#!/usr/bin/env python3
"""
Despliegue del MOTOR DE COTIZACIÓN (personalización) en Odoo.

Crea de forma IDEMPOTENTE todo lo que el motor necesita: modelos, campos
(incluidos computed/related), ACLs, Server Actions, vistas, acciones de ventana,
menús, el contacto de personalización externa y los defaults. Al final corre un
SMOKE TEST y escribe un MANIFIESTO para poder revertir con
`scripts/rollback_motor_cotizacion.py`.

Por qué XML-RPC y no JSON-2: crear metadata (ir.model, ir.model.fields, vistas)
requiere permisos de administrador que el usuario JSON-2 reducido no tiene.

    DRY-RUN POR DEFECTO. Sin --apply no escribe absolutamente nada.

Uso:
    python scripts/deploy_motor_cotizacion.py --target test            # simulacro
    python scripts/deploy_motor_cotizacion.py --target test --apply    # ejecuta en STAGING
    python scripts/deploy_motor_cotizacion.py --target prod            # simulacro en prod
    python scripts/deploy_motor_cotizacion.py --target prod --apply --si-produccion
    python scripts/deploy_motor_cotizacion.py --target prod --verificar  # salud, solo lectura

Variables de entorno (analysis/supplier-sync/.env):
    ODOO_URL, ODOO_TEST_URL, ODOO_DB, ODOO_USER, ODOO_PASSWORD

Notas de compatibilidad (verificado 2026-08-13):
    producción = 19.0+e, staging = saas~19.2+e. El preflight comprueba las
    capacidades que el motor necesita y ABORTA si la versión destino no las tiene
    (en particular: campos manuales COMPUTED, que en prod aún no se usaban).
"""

from __future__ import annotations

import argparse
import io
import json
import os
import sys
import xmlrpc.client
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

# La consola de Windows (cp1252) no puede imprimir '≤', 'ó', etc. y reventaría el
# despliegue a media ejecución. Forzamos UTF-8 en la salida.
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

REPO = Path(__file__).resolve().parent.parent
ACTIONS_DIR = REPO / "odoo-extensions" / "server-actions"
BACKUP_DIR = REPO / "backups"
MARKUP = 1.275
PARTNER_EXTERNO = "Personalización Externa (Mozaprint)"

# Renombres de alcance aplicados en staging (deben viajar a prod). Ver changelog v36.
RENAMES = {
    "Bolsas ≤603 cm²": "Bolsas (Textiles) máximo 603 cm2",
    "Bolsas >603 cm²": "Bolsas (Textiles) mayor a 603 cm2",
}

# Modelos del motor que tienen campo `active`. Odoo OCULTA los archivados en `search`
# (active_test), así que hay que buscarlos explícitamente: si no, el deploy no ve el
# objeto desactivado y crea un DUPLICADO en vez de repararlo.
# Escenario real que esto cubre: un upgrade de Odoo desactiva la vista heredada cuando
# su xpath deja de resolver. La reparación correcta es reactivarla, no crear otra.
ARCHIVABLES = {"ir.ui.view", "ir.ui.menu", "res.partner"}
CTX_ARCHIVADOS = {"context": {"active_test": False}}


# ---------------------------------------------------------------- conexión ---
class Odoo:
    """Cliente XML-RPC admin con interruptor de dry-run: en simulacro, toda
    escritura se registra y se devuelve un id ficticio, nunca llega a Odoo."""

    def __init__(self, url: str, db: str, user: str, pwd: str, apply: bool):
        self.url, self.db, self.pwd, self.apply = url.rstrip("/"), db, pwd, apply
        self.uid = xmlrpc.client.ServerProxy(f"{self.url}/xmlrpc/2/common").authenticate(db, user, pwd, {})
        if not self.uid:
            raise SystemExit(f"✗ Autenticación fallida en {self.url} (db={db})")
        self._m = xmlrpc.client.ServerProxy(f"{self.url}/xmlrpc/2/object")
        self._sim = 0
        self.cambios: list[str] = []
        # Modelos que en DRY-RUN "se crearían": permiten simular sus campos/ACLs sin
        # abortar. Sin esto el simulacro solo funcionaría donde los modelos YA existen,
        # es decir, nunca en la base limpia donde de verdad hace falta.
        self.simulados: set[str] = set()

    def read_call(self, model: str, method: str, *args, **kw):
        return self._m.execute_kw(self.db, self.uid, self.pwd, model, method, list(args), kw)

    def write_call(self, model: str, method: str, *args, **kw):
        if not self.apply:
            self._sim -= 1
            return [self._sim] if method == "create" else True
        return self._m.execute_kw(self.db, self.uid, self.pwd, model, method, list(args), kw)

    def version(self) -> str:
        return xmlrpc.client.ServerProxy(f"{self.url}/xmlrpc/2/common").version().get("server_serie", "?")

    def xmlid(self, module: str, name: str):
        d = self.read_call("ir.model.data", "search_read",
                           [["module", "=", module], ["name", "=", name]], fields=["res_id"])
        return d[0]["res_id"] if d else None


def _id(res):
    return res[0] if isinstance(res, list) and res else res


# ------------------------------------------------------------- definiciones ---
# (modelo, nombre, tipo, etiqueta, extras)
CAMPOS: list[tuple] = [
    # --- x_approval_request ---
    ("x_approval_request", "x_sale_order_id", "many2one", "Cotización",
     {"relation": "sale.order", "required": True, "on_delete": "cascade"}),
    ("x_approval_request", "x_sale_order_line_id", "many2one", "Línea de producto (origen)",
     {"relation": "sale.order.line", "on_delete": "cascade"}),
    ("x_approval_request", "x_channel_id", "many2one", "Conversación WA",
     {"relation": "discuss.channel", "on_delete": "set null"}),
    ("x_approval_request", "x_tecnica_id", "many2one", "Técnica",
     {"relation": "x_tecnica_personalizacion", "on_delete": "set null"}),
    ("x_approval_request", "x_qty", "integer", "Cantidad", {}),
    ("x_approval_request", "x_tintas", "integer", "Número de tintas", {}),
    ("x_approval_request", "x_reason", "text", "Razón de aprobación necesaria", {}),
    ("x_approval_request", "x_context_json", "text", "Contexto serializado", {}),
    ("x_approval_request", "x_requested_at", "datetime", "Solicitado en", {}),
    ("x_approval_request", "x_responded_at", "datetime", "Respondido en", {}),
    ("x_approval_request", "x_responded_by_id", "many2one", "Respondido por",
     {"relation": "res.users", "on_delete": "set null"}),
    ("x_approval_request", "x_status", "selection", "Estado",
     {"selection_pairs": [("pending", "Pendiente"), ("approved", "Aprobada"), ("rejected", "Rechazada")]}),
    ("x_approval_request", "x_approved_cost_unit", "float", "Costo unitario aprobado", {}),
    ("x_approval_request", "x_approved_setup_cost", "float", "Costo de setup aprobado", {}),
    ("x_approval_request", "x_approved_unidad", "selection", "Unidad del costo aprobado",
     {"selection_pairs": [("pieza", "Por pieza"), ("lote", "Por lote")]}),
    ("x_approval_request", "x_approved_servicio_id", "many2one", "Servicio aplicado",
     {"relation": "product.product", "on_delete": "set null"}),
    ("x_approval_request", "x_markup", "float", "Markup (factor sobre el costo)", {}),
    ("x_approval_request", "x_approved_precio_venta", "float", "Precio de venta (calculado)",
     {"store": True, "readonly": False, "depends": "x_approved_cost_unit,x_markup",
      "compute": "for r in self:\n    r['x_approved_precio_venta'] = round((r.x_approved_cost_unit or 0.0) * (r.x_markup or %s), 2)\n" % MARKUP}),
    ("x_approval_request", "x_approved_precio_setup", "float", "Precio de venta del setup (calculado)",
     {"store": True, "readonly": False, "depends": "x_approved_setup_cost,x_markup",
      "compute": "for r in self:\n    r['x_approved_precio_setup'] = round((r.x_approved_setup_cost or 0.0) * (r.x_markup or %s), 2)\n" % MARKUP}),
    ("x_approval_request", "x_guardar_tarifa", "selection", "¿Guardar esta tarifa en la matriz de costos?",
     {"selection_pairs": [("no", "No guardar (solo esta cotización)"),
                          ("proveedor", "Guardar como tarifa del proveedor del producto"),
                          ("externo", "Guardar como tarifa de personalización EXTERNA")]}),
    ("x_approval_request", "x_alcance_nuevo", "char", "Alcance de la nueva tarifa", {}),
    ("x_approval_request", "x_tarifa_qty_from", "integer", "Tarifa: cantidad desde", {}),
    ("x_approval_request", "x_tarifa_qty_to", "integer", "Tarifa: cantidad hasta (0 = sin límite)", {}),
    ("x_approval_request", "x_notes", "text", "Notas internas", {}),
    ("x_approval_request", "x_assigned_user_id", "many2one", "Asignado a",
     {"relation": "res.users", "on_delete": "set null"}),
    # --- sale.order ---
    ("sale.order", "x_requires_human_approval", "boolean", "Requiere aprobación humana", {}),
    ("sale.order", "x_approval_request_id", "many2one", "Solicitud de aprobación",
     {"relation": "x_approval_request", "on_delete": "set null"}),
    ("sale.order", "x_customization_cost_source", "selection", "Fuente del costo de personalización",
     {"selection_pairs": [("parametrized", "Parametrizado en sistema"),
                          ("manually_approved", "Aprobado manualmente"), ("no_aplica", "No aplica")]}),
    # --- sale.order.line ---
    ("sale.order.line", "x_source_line_id", "many2one", "Línea de producto origen (personalización)",
     {"relation": "sale.order.line", "on_delete": "cascade"}),
    ("sale.order.line", "x_es_setup", "boolean", "Es línea de setup (personalización)", {}),
    # --- x_costo_personalizacion ---
    ("x_costo_personalizacion", "x_personalizacion_externa", "boolean",
     "Personalización externa (no ligada al proveedor del producto)", {}),
    ("x_costo_personalizacion", "x_markup", "float", "Markup (factor sobre el costo)", {}),
    ("x_costo_personalizacion", "x_precio_venta", "float", "Precio de venta (MXN)",
     {"store": True, "readonly": False, "depends": "x_costo_unit,x_markup",
      "compute": "for r in self:\n    r['x_precio_venta'] = round((r.x_costo_unit or 0.0) * (r.x_markup or %s), 2)\n" % MARKUP}),
    ("x_costo_personalizacion", "x_precio_setup", "float", "Precio de venta del setup (MXN)",
     {"store": True, "readonly": False, "depends": "x_costo_setup,x_markup",
      "compute": "for r in self:\n    r['x_precio_setup'] = round((r.x_costo_setup or 0.0) * (r.x_markup or %s), 2)\n" % MARKUP}),
    # --- x_wizard_personalizacion (transitorio) ---
    ("x_wizard_personalizacion", "x_order_id", "many2one", "Cotización",
     {"relation": "sale.order", "on_delete": "cascade"}),
    ("x_wizard_personalizacion", "x_sale_order_line_id", "many2one", "Línea de cotización",
     {"relation": "sale.order.line", "on_delete": "cascade"}),
    ("x_wizard_personalizacion", "x_producto_id", "many2one", "Producto",
     {"relation": "product.product", "on_delete": "set null", "store": False, "readonly": True,
      "related": "x_sale_order_line_id.product_id"}),
    ("x_wizard_personalizacion", "x_proveedor_id", "many2one", "Proveedor del producto",
     {"relation": "res.partner", "on_delete": "set null", "store": False, "readonly": True,
      "related": "x_sale_order_line_id.product_id.seller_ids.partner_id"}),
    ("x_wizard_personalizacion", "x_tecnicas_producto_ids", "many2many", "Técnicas del producto",
     {"relation": "x_tecnica_personalizacion", "store": False, "readonly": True,
      "related": "x_sale_order_line_id.product_id.product_tmpl_id.x_tecnicas_compatibles_ids"}),
    ("x_wizard_personalizacion", "x_tecnica_id", "many2one", "Técnica",
     {"relation": "x_tecnica_personalizacion", "on_delete": "cascade", "store": True, "readonly": False,
      "depends": "x_sale_order_line_id",
      "compute": "for r in self:\n    r['x_tecnica_id'] = r.x_sale_order_line_id.product_id.product_tmpl_id.x_tecnica_default_id\n"}),
    ("x_wizard_personalizacion", "x_qty", "integer", "Cantidad",
     {"store": True, "readonly": False, "depends": "x_sale_order_line_id",
      "compute": "for r in self:\n    r['x_qty'] = int(r.x_sale_order_line_id.product_uom_qty or 0)\n"}),
    ("x_wizard_personalizacion", "x_tintas", "integer", "Número de tintas", {}),
    ("x_wizard_personalizacion", "x_posiciones", "integer", "Número de posiciones", {}),
    ("x_wizard_personalizacion", "x_area_cm2", "float", "Área (cm²)", {}),
    ("x_wizard_personalizacion", "x_aviso_tecnica", "char", "¿Asignada al producto?",
     {"store": False, "readonly": True, "depends": "x_sale_order_line_id,x_tecnica_id",
      "compute": ("for r in self:\n"
                  "    comp = r.x_sale_order_line_id.product_id.product_tmpl_id.x_tecnicas_compatibles_ids\n"
                  "    if not r.x_tecnica_id or not r.x_sale_order_line_id:\n"
                  "        r['x_aviso_tecnica'] = ''\n"
                  "    elif r.x_tecnica_id in comp:\n"
                  "        r['x_aviso_tecnica'] = 'OK - tecnica asignada a este producto'\n"
                  "    else:\n"
                  "        r['x_aviso_tecnica'] = 'AVISO - esta tecnica NO esta asignada al producto (verifica o cotiza externo)'\n")}),
    ("x_wizard_personalizacion", "x_candidato_elegido_id", "many2one", "Candidato elegido",
     {"relation": "x_costo_personalizacion", "on_delete": "set null"}),
    ("x_wizard_personalizacion", "x_candidato_externo_id", "many2one", "Proveedor externo (opcional)",
     {"relation": "x_costo_personalizacion", "on_delete": "set null"}),
    ("x_wizard_personalizacion", "x_forzar_aprobacion", "boolean",
     "Ninguna tarifa aplica - solicitar aprobación", {}),
    ("x_wizard_personalizacion", "x_msg_confirmacion", "text", "Aviso", {}),
]

# (clave, nombre visible, archivo .py, modelo)
#
# `abrir_wizard_personalizacion_por_linea.py` NO se despliega a propósito (decisión JC
# 2026-08-14): está probado y versionado, pero ningún botón lo llama — Studio no permite
# agregar botones a la lista de líneas del pedido. Para habilitarlo el día que se pueda,
# basta con volver a agregar su tupla aquí y re-correr el deploy.
SERVER_ACTIONS = [
    ("apply", "Agregar personalización (motor cotización)", "agregar_personalizacion.py", "x_wizard_personalizacion"),
    ("confirmar", "Confirmar solicitud de aprobación", "confirmar_aprobacion.py", "x_wizard_personalizacion"),
    ("opener", "Abrir wizard personalización (pedido)", "abrir_wizard_personalizacion.py", "sale.order"),
    ("aprobar", "Aprobar personalización y agregar a cotización", "aprobar_personalizacion.py", "x_approval_request"),
    ("rechazar", "Rechazar personalización", "rechazar_personalizacion.py", "x_approval_request"),
]


def limpiar_codigo(src: str) -> str:
    """Quita comentarios y líneas en blanco para que Odoo reciba solo código ejecutable.
    El repo conserva la documentación completa; esto solo afecta lo que se sube.

    Conservador a propósito: solo elimina líneas cuyo PRIMER carácter no-espacio es '#'.
    No toca comentarios al final de una línea de código ni cadenas de texto (por eso una
    línea con un '#' dentro de un string nunca se pierde)."""
    fuera = []
    for linea in src.splitlines():
        sin_esp = linea.strip()
        if not sin_esp or sin_esp.startswith("#"):
            continue
        fuera.append(linea)
    return "\n".join(fuera) + "\n"


def vistas(aid: dict) -> list[dict]:
    """Definición de vistas. `aid` mapea clave de Server Action -> id real."""
    from views_motor import ARCHS  # noqa: F401  (mismo directorio)
    return ARCHS(aid)


# ------------------------------------------------------------------- pasos ---
def preflight(o: Odoo, target: str) -> list[str]:
    """Comprobaciones previas. Devuelve lista de problemas BLOQUEANTES."""
    problemas = []
    print(f"\n=== PREFLIGHT ({target}) ===")
    print(f"  Odoo {o.version()}  ·  {o.url}  ·  db={o.db}  ·  uid={o.uid}")

    fg = o.read_call("ir.model.fields", "fields_get", [], ["type"])
    faltan = [c for c in ("compute", "depends", "related", "store", "readonly", "on_delete", "selection_ids")
              if c not in fg]
    if faltan:
        problemas.append(f"ir.model.fields no soporta {faltan}: esta versión no admite los campos del motor")
    print(f"  · ir.model.fields soporta compute/related: {'SÍ' if not faltan else 'NO ' + str(faltan)}")

    if not o.read_call("ir.ui.view", "search_count", [["type", "=", "list"]]):
        problemas.append("la instancia no usa vistas type='list' (¿versión < 17?)")

    for mod, name in (("sale", "view_order_form"), ("sale", "menu_sale_config"),
                      ("sale", "sale_menu_root"), ("base", "group_user")):
        if not o.xmlid(mod, name):
            problemas.append(f"falta el xmlid {mod}.{name}")

    for m in ("x_tecnica_personalizacion", "x_costo_personalizacion"):
        if not o.read_call("ir.model", "search_count", [["model", "=", m]]):
            problemas.append(f"falta el modelo prerequisito {m} (cárgalo antes del motor)")

    n_serv = o.read_call("product.product", "search_count", [["x_es_servicio_personalizacion", "=", True]])
    if not n_serv:
        problemas.append("no hay servicios de personalización (corre seed_servicios_personalizacion.py)")
    print(f"  · prerequisitos: {n_serv} servicios, "
          f"{o.read_call('x_tecnica_personalizacion','search_count',[['x_activa','=',True]])} técnicas, "
          f"{o.read_call('x_costo_personalizacion','search_count',[])} tarifas")

    for l in problemas:
        print(f"  ✗ {l}")
    return problemas


def probe_computed(o: Odoo) -> bool:
    """PRUEBA DE FALLO: verifica que esta versión SÍ calcula campos manuales computed.
    Crea un campo desechable sobre el modelo transitorio, lo lee y lo borra.
    Solo se ejecuta con --apply (en dry-run se informa que queda pendiente)."""
    if not o.apply:
        print("  · (dry-run) prueba de campos computed: se hará al aplicar")
        return True
    mid = _id(o.read_call("ir.model", "search", [["model", "=", "x_wizard_personalizacion"]]))
    # OJO: la prueba corre ANTES de crear los campos del motor, así que no puede depender
    # de ninguno de ellos. Se usa 'create_date' (existe en cualquier modelo) — si se pone
    # un campo custom aquí, en una base limpia Odoo responde "Campo desconocido ... en la
    # dependencia" y aborta el despliegue (pasó en el ensayo del 2026-08-14).
    fid = _id(o.write_call("ir.model.fields", "create", [{
        "name": "x_probe_computed", "field_description": "probe", "model_id": mid, "ttype": "integer",
        "state": "manual", "store": True, "readonly": True, "depends": "create_date",
        "compute": "for r in self:\n    r['x_probe_computed'] = 6 * 7\n"}]))
    try:
        wid = _id(o.write_call("x_wizard_personalizacion", "create", [{}]))
        val = o.read_call("x_wizard_personalizacion", "read", [wid], fields=["x_probe_computed"])[0]["x_probe_computed"]
        o.write_call("x_wizard_personalizacion", "unlink", [wid])
        ok = val == 42
        print(f"  · prueba de campos computed: {'OK (6x7=42)' if ok else f'FALLÓ (devolvió {val})'}")
        return ok
    finally:
        o.write_call("ir.model.fields", "unlink", [fid])


def ensure_model(o: Odoo, tech: str, label: str, transient: bool, man: dict) -> int:
    ids = o.read_call("ir.model", "search", [["model", "=", tech]])
    if ids:
        print(f"  [ ok] modelo {tech}")
        return ids[0]
    vals = {"name": label, "model": tech, "state": "manual"}
    if transient:
        vals["transient"] = True
    nid = _id(o.write_call("ir.model", "create", [vals]))
    if not o.apply:
        o.simulados.add(tech)
    else:
        man["models"].append({"model": tech, "id": nid})
    o.cambios.append(f"CREAR modelo {tech}")
    print(f"  [NEW] modelo {tech}{'' if o.apply else ' (simulado)'}")
    return nid


def ensure_field(o: Odoo, model: str, name: str, ttype: str, label: str, extra: dict, man: dict):
    ids = o.read_call("ir.model.fields", "search", [["model", "=", model], ["name", "=", name]])
    if ids:
        print(f"  [ ok] {model}.{name}")
        return ids[0]
    mids = o.read_call("ir.model", "search", [["model", "=", model]])
    if not mids:
        if model in o.simulados:      # dry-run sobre un modelo que se crearía en este mismo run
            o.cambios.append(f"CREAR campo {model}.{name}")
            print(f"  [NEW] {model}.{name} (simulado)")
            return None
        raise SystemExit(f"✗ modelo {model} no existe al crear {name}")
    vals = {"name": name, "field_description": label, "model_id": mids[0], "ttype": ttype,
            "state": "manual", "store": extra.get("store", True),
            "required": extra.get("required", False)}
    for k in ("relation", "on_delete", "compute", "depends"):
        if extra.get(k):
            vals[k] = extra[k]
    if "readonly" in extra:
        vals["readonly"] = extra["readonly"]
    if extra.get("related"):
        vals["related"] = extra["related"]
    if extra.get("selection_pairs"):
        vals["selection_ids"] = [(0, 0, {"value": v, "name": n, "sequence": (i + 1) * 10})
                                 for i, (v, n) in enumerate(extra["selection_pairs"])]
    nid = _id(o.write_call("ir.model.fields", "create", [vals]))
    man["fields"].append({"model": model, "name": name, "id": nid})
    o.cambios.append(f"CREAR campo {model}.{name}")
    print(f"  [NEW] {model}.{name} (id={nid})")
    return nid


def ensure_acl(o: Odoo, model: str, group_id: int, man: dict):
    mid = _id(o.read_call("ir.model", "search", [["model", "=", model]]))
    if not mid:
        if model in o.simulados:
            o.cambios.append(f"CREAR ACL {model}")
            print(f"  [NEW] ACL {model} (simulado)")
            return None
        raise SystemExit(f"✗ modelo {model} no existe al crear su ACL")
    ex = o.read_call("ir.model.access", "search", [["model_id", "=", mid], ["group_id", "=", group_id]])
    if ex:
        print(f"  [ ok] ACL {model}")
        return ex[0]
    nid = _id(o.write_call("ir.model.access", "create", [{
        "name": f"{model}.user", "model_id": mid, "group_id": group_id,
        "perm_read": True, "perm_write": True, "perm_create": True, "perm_unlink": True}]))
    man["acls"].append({"model": model, "id": nid})
    o.cambios.append(f"CREAR ACL {model}")
    print(f"  [NEW] ACL {model} (id={nid})")
    return nid


def upsert(o: Odoo, model: str, domain: list, vals: dict, etiqueta: str, man: dict, key: str):
    arch = model in ARCHIVABLES
    ids = o.read_call(model, "search", domain, **(CTX_ARCHIVADOS if arch else {}))
    if ids:
        nota = "actualizado"
        if arch:
            # Se fuerza active=True: re-correr el deploy es el procedimiento de
            # reparación cuando un upgrade deja algo desactivado (ver ARCHIVABLES).
            vals = {**vals, "active": True}
            if not o.read_call(model, "read", ids[:1], fields=["active"])[0]["active"]:
                nota = "REACTIVADO (estaba desactivado)"
                o.cambios.append(f"REACTIVAR {etiqueta}")
        o.write_call(model, "write", ids, vals)
        print(f"  [ ok] {etiqueta} (id={ids[0]}, {nota})")
        return ids[0]
    nid = _id(o.write_call(model, "create", [vals]))
    man[key].append({"model": model, "id": nid, "label": etiqueta})
    o.cambios.append(f"CREAR {etiqueta}")
    print(f"  [NEW] {etiqueta} (id={nid})")
    return nid


def inventariar(o: Odoo, target: str) -> dict:
    """Construye un manifiesto a partir de lo que YA existe en la instancia.

    Sirve para dos cosas: ensayar el rollback sobre un despliegue hecho a mano (staging)
    y recuperar la capacidad de revertir si se pierde el manifiesto de un deploy real."""
    man = {"target": target, "url": o.url, "db": o.db, "ts": datetime.now().isoformat(timespec="seconds"),
           "models": [], "fields": [], "acls": [], "actions": [], "views": [], "menus": [],
           "partners": [], "defaults": [], "data_backup": None}

    for tech in ("x_approval_request", "x_wizard_personalizacion"):
        for i in o.read_call("ir.model", "search", [["model", "=", tech]]):
            man["models"].append({"model": tech, "id": i})
    for model, name, *_ in CAMPOS:
        for i in o.read_call("ir.model.fields", "search", [["model", "=", model], ["name", "=", name]]):
            man["fields"].append({"model": model, "name": name, "id": i})
    for tech in ("x_approval_request", "x_wizard_personalizacion"):
        mid = _id(o.read_call("ir.model", "search", [["model", "=", tech]]))
        if mid:
            for i in o.read_call("ir.model.access", "search", [["model_id", "=", mid]]):
                man["acls"].append({"model": "ir.model.access", "id": i, "label": tech})
    # Incluye también acciones del motor RETIRADAS de SERVER_ACTIONS: si quedaran vivas
    # apuntando a un modelo que el rollback borra, bloquearían el borrado.
    nombres_act = [n for _, n, _, _ in SERVER_ACTIONS] + ["Abrir wizard personalización (por línea)"]
    for a in o.read_call("ir.actions.server", "search_read", [["name", "in", nombres_act]], fields=["name"]):
        man["actions"].append({"model": "ir.actions.server", "id": a["id"], "label": a["name"]})
    for a in o.read_call("ir.actions.act_window", "search_read",
                         [["res_model", "in", ["x_approval_request", "x_costo_personalizacion",
                                               "x_tecnica_personalizacion"]]], fields=["name"]):
        man["actions"].append({"model": "ir.actions.act_window", "id": a["id"], "label": a["name"]})
    # Los tres modelos archivables se buscan incluyendo archivados: si un upgrade
    # desactivó la vista heredada, el manifiesto debe seguir pudiendo borrarla.
    nombres_vista = [v["name"] for v in ARCHS_NOMBRES]
    for v in o.read_call("ir.ui.view", "search_read", [["name", "in", nombres_vista]],
                         fields=["name"], **CTX_ARCHIVADOS):
        man["views"].append({"model": "ir.ui.view", "id": v["id"], "label": v["name"]})
    for mu in o.read_call("ir.ui.menu", "search_read",
                          [["name", "in", ["Aprobaciones personalización", "Costos de personalización",
                                           "Técnicas de personalización"]]],
                          fields=["name"], **CTX_ARCHIVADOS):
        man["menus"].append({"model": "ir.ui.menu", "id": mu["id"], "label": mu["name"]})
    for p in o.read_call("res.partner", "search", [["name", "=", PARTNER_EXTERNO]], **CTX_ARCHIVADOS):
        man["partners"].append({"model": "res.partner", "id": p, "label": PARTNER_EXTERNO})
    for model in ("x_costo_personalizacion", "x_approval_request"):
        f = o.read_call("ir.model.fields", "search", [["model", "=", model], ["name", "=", "x_markup"]])
        if f:
            for d in o.read_call("ir.default", "search", [["field_id", "=", f[0]]]):
                man["defaults"].append({"model": "ir.default", "id": d, "label": f"markup {model}"})

    filas = o.read_call("x_costo_personalizacion", "search_read", [],
                        fields=["id", "x_name", "x_alcance_producto", "x_costo_unit", "x_costo_setup"])
    BACKUP_DIR.mkdir(exist_ok=True)
    b = BACKUP_DIR / f"costos_inventario_{target}_{datetime.now():%Y%m%d_%H%M%S}.json"
    b.write_text(json.dumps(filas, ensure_ascii=False, indent=1), encoding="utf-8")
    man["data_backup"] = str(b)

    print(f"  modelos={len(man['models'])} campos={len(man['fields'])} acls={len(man['acls'])} "
          f"acciones={len(man['actions'])} vistas={len(man['views'])} menús={len(man['menus'])} "
          f"contactos={len(man['partners'])} defaults={len(man['defaults'])}")
    print(f"  respaldo de datos ({len(filas)} filas): {b.name}")
    return man


# Nombres de las vistas (para el inventario, sin necesidad de los ids de las acciones).
ARCHS_NOMBRES = [{"name": n} for n in (
    "x_wizard_personalizacion.form", "x_wizard_personalizacion.confirmar",
    "x_approval_request.list", "x_approval_request.form",
    "x_costo_personalizacion.list", "x_costo_personalizacion.form",
    "x_tecnica_personalizacion.list", "x_tecnica_personalizacion.form",
    "sale.order.personalizar.header.button")]

MENUS_ESPERADOS = ["Aprobaciones personalización", "Costos de personalización",
                   "Técnicas de personalización"]
MODELOS_CON_MENU = ["x_approval_request", "x_costo_personalizacion", "x_tecnica_personalizacion"]
BOTON_HEADER = "Agregar personalización"


# ------------------------------------------------------------- verificación ---
def verificar(o: Odoo, target: str) -> int:
    """Revisión de SALUD del motor. SOLO LECTURA. Devuelve el número de problemas.

    Para correr después de cualquier actualización de Odoo — ver
    `docs/procedimiento-upgrade-odoo.md`. Comprueba tres cosas distintas, de menos
    a más exigente:

      1. que los objetos EXISTAN (un upgrade no los borra, pero conviene confirmarlo);
      2. que los archivables sigan ACTIVOS — Odoo desactiva las vistas heredadas
         cuyo xpath deja de resolver: no se pierde nada, pero el botón se apaga
         para todos y `search` deja de verlas;
      3. que el formulario de ventas RENDERICE el botón. Esta es la prueba de
         verdad: valida que la herencia se aplica, no solo que la vista existe.
    """
    problemas: list[str] = []
    print("\n=== VERIFICACIÓN DE SALUD (solo lectura, no escribe nada) ===")
    print(f"  Odoo {o.version()}  ·  {o.url}  ·  db={o.db}\n")

    def grupo(etiqueta: str, hay: int, esperado: int, detalles: list[str]):
        ok = not detalles and hay == esperado
        print(f"  {'✓' if ok else '✗'} {etiqueta:<24} {hay}/{esperado}")
        for d in detalles:
            print(f"        · {d}")
        problemas.extend(detalles)

    modelos = ("x_approval_request", "x_wizard_personalizacion")
    falta = [f"falta el modelo {m}" for m in modelos
             if not o.read_call("ir.model", "search_count", [["model", "=", m]])]
    grupo("modelos", len(modelos) - len(falta), len(modelos), falta)

    # Los campos se piden por modelo (2-3 llamadas) en vez de uno por uno (49).
    esperados: dict[str, set] = {}
    for m, n, *_ in CAMPOS:
        esperados.setdefault(m, set()).add(n)
    total, falta = sum(len(v) for v in esperados.values()), []
    for m, nombres in esperados.items():
        try:
            hay = {f["name"] for f in o.read_call("ir.model.fields", "search_read",
                                                  [["model", "=", m]], fields=["name"])}
        except xmlrpc.client.Fault:
            hay = set()
        falta += [f"falta el campo {m}.{n}" for n in sorted(nombres - hay)]
    grupo("campos", total - len(falta), total, falta)

    falta = [f"falta el ACL de {m}" for m in modelos
             if not o.read_call("ir.model.access", "search_count", [["model_id.model", "=", m]])]
    grupo("ACLs", len(modelos) - len(falta), len(modelos), falta)

    lineas, falta = 0, []
    for _, nombre, _, _ in SERVER_ACTIONS:
        regs = o.read_call("ir.actions.server", "search_read", [["name", "=", nombre]], fields=["code"])
        if not regs:
            falta.append(f"falta el Server Action «{nombre}»")
        elif not (regs[0]["code"] or "").strip():
            falta.append(f"el Server Action «{nombre}» quedó SIN CÓDIGO")
        else:
            lineas += len(regs[0]["code"].splitlines())
    grupo("Server Actions", len(SERVER_ACTIONS) - len(falta), len(SERVER_ACTIONS), falta)
    print(f"        · {lineas} líneas de Python viviendo dentro de Odoo")

    nombres_v = [v["name"] for v in ARCHS_NOMBRES]
    por_nombre = {r["name"]: r for r in
                  o.read_call("ir.ui.view", "search_read", [["name", "in", nombres_v]],
                              fields=["name", "active"], **CTX_ARCHIVADOS)}
    falta = []
    for n in nombres_v:
        r = por_nombre.get(n)
        if not r:
            falta.append(f"falta la vista {n}")
        elif not r["active"]:
            falta.append(f"la vista {n} está DESACTIVADA (típico tras un upgrade)")
    grupo("vistas", len(nombres_v) - len(falta), len(nombres_v), falta)

    hay = o.read_call("ir.actions.act_window", "search_count", [["res_model", "in", MODELOS_CON_MENU]])
    grupo("acciones de ventana", hay, 3, [] if hay >= 3 else [f"solo hay {hay} de 3"])

    por_nombre = {r["name"]: r for r in
                  o.read_call("ir.ui.menu", "search_read", [["name", "in", MENUS_ESPERADOS]],
                              fields=["name", "active"], **CTX_ARCHIVADOS)}
    falta = []
    for n in MENUS_ESPERADOS:
        r = por_nombre.get(n)
        if not r:
            falta.append(f"falta el menú «{n}»")
        elif not r["active"]:
            falta.append(f"el menú «{n}» está ARCHIVADO")
    grupo("menús", len(MENUS_ESPERADOS) - len(falta), len(MENUS_ESPERADOS), falta)

    regs = o.read_call("res.partner", "search_read", [["name", "=", PARTNER_EXTERNO]],
                       fields=["active"], **CTX_ARCHIVADOS)
    falta = ([] if regs and regs[0]["active"]
             else [f"falta el contacto «{PARTNER_EXTERNO}»"] if not regs
             else [f"el contacto «{PARTNER_EXTERNO}» está ARCHIVADO"])
    grupo("contacto externo", 0 if falta else 1, 1, falta)

    hay = 0
    for m in ("x_costo_personalizacion", "x_approval_request"):
        f = o.read_call("ir.model.fields", "search", [["model", "=", m], ["name", "=", "x_markup"]])
        if f and o.read_call("ir.default", "search_count", [["field_id", "=", f[0]]]):
            hay += 1
    grupo("defaults de markup", hay, 2, [] if hay == 2 else [f"solo hay {hay} de 2 defaults"])

    # --- La prueba de verdad: ¿el formulario de ventas abre y muestra el botón? ---
    print("\n  --- prueba funcional ---")
    try:
        arch = json.dumps(o.read_call("sale.order", "get_views", [[False, "form"]]), ensure_ascii=False)
        if BOTON_HEADER in arch:
            print(f"  ✓ el formulario de ventas renderiza el botón «{BOTON_HEADER}»")
        else:
            problemas.append("el formulario de ventas ABRE pero NO muestra el botón: la vista "
                             "heredada existe y su xpath ya no aplica")
            print(f"  ✗ el formulario de ventas NO muestra «{BOTON_HEADER}»")
    except xmlrpc.client.Fault as e:
        msg = e.faultString.strip().splitlines()[-1][:120]
        problemas.append(f"el formulario de ventas NO ABRE: {msg}")
        print(f"  ✗ el formulario de ventas NO ABRE → {msg}")

    # --- Datos (informativo; solo el markup faltante cuenta como problema) ---
    print("\n  --- datos ---")
    try:
        tarifas = o.read_call("x_costo_personalizacion", "search_count", [])
        sin_mk = o.read_call("x_costo_personalizacion", "search_count", [["x_markup", "<=", 0]])
        pend = o.read_call("x_approval_request", "search_count", [["x_status", "=", "pending"]])
        usos = o.read_call("sale.order.line", "search_count", [["x_source_line_id", "!=", False]])
        print(f"  · {tarifas} tarifas en la matriz · {pend} aprobaciones pendientes "
              f"· {usos} líneas de personalización en cotizaciones")
        if sin_mk:
            problemas.append(f"{sin_mk} tarifas sin markup (no calculan precio de venta)")
            print(f"  ✗ {sin_mk} tarifas SIN markup")
    except xmlrpc.client.Fault as e:
        print(f"  ⚠ no se pudieron leer los datos: {e.faultString.strip().splitlines()[-1][:90]}")

    prod = " --si-produccion" if target == "prod" else ""
    print("\n" + "=" * 74)
    if problemas:
        print(f"  ✗ {len(problemas)} PROBLEMA(S): el motor NO está completo.")
        print(f"     Reparar: python scripts/deploy_motor_cotizacion.py --target {target} "
              f"--apply{prod} --saltar-datos")
        print("     Procedimiento completo: docs/procedimiento-upgrade-odoo.md")
    else:
        print("  ✓ El motor está completo y operativo.")
    print("=" * 74)
    return len(problemas)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--target", choices=("test", "prod"), required=True)
    ap.add_argument("--apply", action="store_true", help="ejecuta (sin esto: simulacro)")
    ap.add_argument("--si-produccion", action="store_true", help="confirmación extra obligatoria para prod")
    ap.add_argument("--saltar-datos", action="store_true", help="no tocar datos (markup/renombres)")
    ap.add_argument("--saltar-smoke", action="store_true", help="no correr el smoke test")
    ap.add_argument("--con-comentarios", action="store_true",
                    help="sube el código con comentarios (por defecto se quitan para "
                         "minimizar las líneas dentro de Odoo)")
    ap.add_argument("--inventario", action="store_true",
                    help="NO despliega: escribe un manifiesto de lo que ya existe "
                         "(para revertir un despliegue hecho a mano o recuperar un manifiesto perdido)")
    ap.add_argument("--verificar", action="store_true",
                    help="NO despliega: revisión de salud de solo lectura. Sale con código 1 "
                         "si falta o está desactivado algo. Correr tras cada upgrade de Odoo.")
    args = ap.parse_args()

    load_dotenv(REPO / "analysis" / "supplier-sync" / ".env")
    if args.target == "prod":
        url, db = os.environ["ODOO_URL"], os.environ["ODOO_DB"]
        if args.apply and not args.si_produccion:
            print("✗ Para escribir en PRODUCCIÓN agrega --si-produccion (guardarraíl).", file=sys.stderr)
            return 2
    else:
        url = os.environ["ODOO_TEST_URL"]
        db = url.rstrip("/").split("//")[1].split(".")[0]  # el subdominio ES la BD en staging

    o = Odoo(url, db, os.environ["ODOO_USER"], os.environ["ODOO_PASSWORD"], args.apply)
    modo = "APLICAR" if args.apply else "DRY-RUN (no escribe)"
    print("=" * 74)
    print(f"  MOTOR DE COTIZACIÓN — despliegue  [{args.target.upper()}]  ·  {modo}")
    print(f"  {o.url}  (db={db})")
    print("=" * 74)

    if args.verificar:
        return 1 if verificar(o, args.target) else 0

    if args.inventario:
        print("\n=== INVENTARIO (no despliega) ===")
        man = inventariar(o, args.target)
        BACKUP_DIR.mkdir(exist_ok=True)
        p = BACKUP_DIR / f"manifiesto_INVENTARIO_{args.target}_{datetime.now():%Y%m%d_%H%M%S}.json"
        p.write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"\n  Manifiesto: {p}")
        return 0

    if preflight(o, args.target):
        print("\n✗ ABORTADO: corrige los problemas de preflight antes de desplegar.")
        return 1

    man = {"target": args.target, "url": o.url, "db": db, "ts": datetime.now().isoformat(timespec="seconds"),
           "models": [], "fields": [], "acls": [], "actions": [], "views": [], "menus": [],
           "partners": [], "defaults": [], "data_backup": None}

    # 0. Respaldo de la matriz de costos ANTES de tocar datos
    if not args.saltar_datos:
        filas = o.read_call("x_costo_personalizacion", "search_read", [],
                            fields=["id", "x_name", "x_alcance_producto", "x_costo_unit", "x_costo_setup"])
        BACKUP_DIR.mkdir(exist_ok=True)
        bpath = BACKUP_DIR / f"costos_pre_motor_{args.target}_{datetime.now():%Y%m%d_%H%M%S}.json"
        if args.apply:
            bpath.write_text(json.dumps(filas, ensure_ascii=False, indent=1), encoding="utf-8")
        man["data_backup"] = str(bpath)
        print(f"\n=== RESPALDO ===\n  {len(filas)} filas de costo -> {bpath.name}"
              f"{'' if args.apply else '  (dry-run: no escrito)'}")

    print("\n=== MODELOS ===")
    ensure_model(o, "x_approval_request", "Solicitud de aprobación", False, man)
    ensure_model(o, "x_wizard_personalizacion", "Wizard personalización", True, man)

    # Los ACLs van ANTES de la prueba: en una base limpia, sin ellos ni el admin puede
    # crear el registro desechable que la prueba necesita ("Ningún grupo permite esta
    # operación"). Solo dependen de que los modelos existan. (Ensayo 2026-08-14.)
    print("\n=== ACLs ===")
    gid = o.xmlid("base", "group_user")
    for m in ("x_approval_request", "x_wizard_personalizacion"):
        ensure_acl(o, m, gid, man)

    if not probe_computed(o):
        print("\n✗ ABORTADO: esta versión de Odoo no calcula campos manuales computed.")
        print("  Ejecuta scripts/rollback_motor_cotizacion.py con el manifiesto para limpiar.")
        _guardar_manifiesto(man, args)
        return 1

    print("\n=== CAMPOS ===")
    for model, name, ttype, label, extra in CAMPOS:
        ensure_field(o, model, name, ttype, label, extra, man)

    print("\n=== CONTACTO EXTERNO Y DEFAULTS ===")
    pid = upsert(o, "res.partner", [["name", "=", PARTNER_EXTERNO]],
                 {"name": PARTNER_EXTERNO, "supplier_rank": 0,
                  "comment": "Proveedor de personalización interno/maquila. NO surte productos."},
                 f"partner {PARTNER_EXTERNO}", man, "partners")
    for model in ("x_costo_personalizacion", "x_approval_request"):
        f = o.read_call("ir.model.fields", "search", [["model", "=", model], ["name", "=", "x_markup"]])
        if not f:
            # El campo se crea en este mismo run (dry-run): el default también haría falta.
            o.cambios.append(f"CREAR default markup en {model}")
            print(f"  [NEW] default markup={MARKUP} en {model} (simulado)")
        elif not o.read_call("ir.default", "search", [["field_id", "=", f[0]]]):
            nid = _id(o.write_call("ir.default", "create", [{"field_id": f[0], "json_value": str(MARKUP)}]))
            man["defaults"].append({"model": model, "id": nid})
            o.cambios.append(f"CREAR default markup en {model}")
            print(f"  [NEW] default markup={MARKUP} en {model}")
        else:
            print(f"  [ ok] default markup en {model}")

    print("\n=== SERVER ACTIONS ===")
    aid = {}
    brutas = limpias = 0
    for clave, nombre, archivo, modelo in SERVER_ACTIONS:
        src = (ACTIONS_DIR / archivo).read_text(encoding="utf-8")
        code = src if args.con_comentarios else limpiar_codigo(src)
        brutas += len(src.splitlines())
        limpias += len(code.splitlines())
        mid = _id(o.read_call("ir.model", "search", [["model", "=", modelo]]))
        if not mid and modelo not in o.simulados:
            raise SystemExit(f"✗ modelo {modelo} no existe al crear la acción {nombre}")
        aid[clave] = upsert(o, "ir.actions.server", [["name", "=", nombre]],
                            {"name": nombre, "model_id": mid, "state": "code", "code": code},
                            f"action {nombre}", man, "actions")
    print(f"  Líneas subidas a Odoo: {limpias}"
          + ("" if args.con_comentarios else f" (de {brutas} en el repo; "
             f"−{brutas - limpias} de comentarios/blancos)"))

    print("\n=== VISTAS ===")
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from views_motor import ARCHS
    for v in ARCHS(aid, o):
        dom = [["name", "=", v["name"]]]
        upsert(o, "ir.ui.view", dom, v["vals"], f"vista {v['name']}", man, "views")

    print("\n=== ACCIONES DE VENTANA Y MENÚS ===")
    cfg, root = o.xmlid("sale", "menu_sale_config"), o.xmlid("sale", "sale_menu_root")
    for nombre, modelo, padre, seq in (("Aprobaciones de personalización", "x_approval_request", root, 90),
                                       ("Costos de personalización", "x_costo_personalizacion", cfg, 80),
                                       ("Técnicas de personalización", "x_tecnica_personalizacion", cfg, 81)):
        act = upsert(o, "ir.actions.act_window", [["name", "=", nombre]],
                     {"name": nombre, "res_model": modelo, "view_mode": "list,form"},
                     f"act_window {nombre}", man, "actions")
        menu_nombre = nombre.replace("Aprobaciones de personalización", "Aprobaciones personalización")
        upsert(o, "ir.ui.menu", [["name", "=", menu_nombre]],
               {"name": menu_nombre, "parent_id": padre, "sequence": seq,
                "action": f"ir.actions.act_window,{act}"}, f"menú {menu_nombre}", man, "menus")

    if not args.saltar_datos:
        print("\n=== DATOS ===")
        ids = o.read_call("x_costo_personalizacion", "search", [])
        o.write_call("x_costo_personalizacion", "write", ids, {"x_markup": MARKUP})
        print(f"  markup {MARKUP} -> {len(ids)} filas")
        for viejo, nuevo in RENAMES.items():
            objetivo = o.read_call("x_costo_personalizacion", "search_read",
                                   [["x_alcance_producto", "=", viejo]], fields=["x_name"])
            for reg in objetivo:
                o.write_call("x_costo_personalizacion", "write", [reg["id"]],
                             {"x_alcance_producto": nuevo, "x_name": reg["x_name"].replace(viejo, nuevo)})
            print(f"  renombre '{viejo}' -> '{nuevo}': {len(objetivo)} filas")
        print("  ⚠ Falta cargar tarifas nuevas: corre seed_costos.py con el CSV de analysis/")

    if not args.saltar_smoke and args.apply:
        print("\n=== SMOKE TEST ===")
        _smoke(o, aid)

    ruta = _guardar_manifiesto(man, args)
    print("\n" + "=" * 74)
    print(f"  {'APLICADO' if args.apply else 'SIMULACRO'} — {len(o.cambios)} cambios "
          f"{'realizados' if args.apply else 'pendientes'}")
    if ruta:
        print(f"  Manifiesto (para rollback): {ruta}")
    if not args.apply:
        print("  Nada se escribió. Re-corre con --apply para ejecutar.")
    print("=" * 74)
    return 0


def _guardar_manifiesto(man: dict, args) -> str | None:
    if not args.apply:
        return None
    BACKUP_DIR.mkdir(exist_ok=True)
    p = BACKUP_DIR / f"manifiesto_motor_{args.target}_{datetime.now():%Y%m%d_%H%M%S}.json"
    p.write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
    return str(p)


def _smoke(o: Odoo, aid: dict):
    """Prueba de humo: cotización desechable -> abrir wizard -> aplicar -> borrar."""
    prod = o.read_call("product.product", "search_read",
                       [["x_es_servicio_personalizacion", "=", False], ["sale_ok", "=", True],
                        ["product_tmpl_id.x_tecnica_default_id", "!=", False],
                        ["product_tmpl_id.seller_ids", "!=", False]],
                       fields=["id", "name"], limit=1)
    cli = o.read_call("res.partner", "search", [["customer_rank", ">", 0]], limit=1)
    if not prod or not cli:
        print("  ⚠ sin producto/cliente para el smoke test; sáltalo con --saltar-smoke")
        return
    oid = _id(o.write_call("sale.order", "create", [{
        "partner_id": cli[0], "order_line": [(0, 0, {"product_id": prod[0]["id"], "product_uom_qty": 100})]}]))
    try:
        act = o.write_call("ir.actions.server", "run", [aid["opener"]],
                           context={"active_id": oid, "active_model": "sale.order", "active_ids": [oid]})
        wid = act.get("res_id")
        w = o.read_call("x_wizard_personalizacion", "read", [wid],
                        fields=["x_producto_id", "x_proveedor_id", "x_tecnica_id", "x_qty"])[0]
        print(f"  wizard: producto={bool(w['x_producto_id'])} proveedor={bool(w['x_proveedor_id'])} "
              f"tecnica={bool(w['x_tecnica_id'])} qty={w['x_qty']}")
        assert w["x_proveedor_id"] and w["x_tecnica_id"], "los campos related/computed NO se resolvieron"
        try:
            o.write_call("ir.actions.server", "run", [aid["apply"]],
                         context={"active_id": wid, "active_model": "x_wizard_personalizacion", "active_ids": [wid]})
            print("  aplicar: OK")
        except xmlrpc.client.Fault as e:
            ultima = e.faultString.strip().splitlines()[-1][:90]
            print(f"  aplicar: respuesta esperable del motor -> {ultima}")
        print("  ✓ SMOKE TEST OK (el motor responde y resuelve los campos)")
    finally:
        o.write_call("sale.order", "unlink", [oid])
        print(f"  cotización de prueba {oid} eliminada")


if __name__ == "__main__":
    sys.exit(main())
