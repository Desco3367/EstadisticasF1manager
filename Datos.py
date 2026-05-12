import os
import json
import webbrowser
from collections import defaultdict

# ================= CONFIGURACIÓN =================
CARPETA_BASE = r"C:\Users\jrvb2\OneDrive\Escritorio\F1 manager liga\Liga_F1_Data"

PUNTOS_CARRERA = {1: 25, 2: 18, 3: 15, 4: 12, 5: 10, 6: 8, 7: 6, 8: 4, 9: 2, 10: 1}
PUNTOS_SPRINT  = {1: 8, 2: 7, 3: 6, 4: 5, 5: 4, 6: 3, 7: 2, 8: 1}
PUNTO_VUELTA_RAPIDA = 1

PILOTOS_EXCLUIDOS = {"Noah Wright", "Felicity Ariss"}
# =================================================

def nombre_corto(carpeta):
    try:
        prefijo = carpeta.split('_')[0]
        return f"T{int(prefijo[1:])}"
    except:
        return carpeta

def formatear_tiempo(ms):
    if ms == 0:
        return ""
    total = ms / 1000.0
    horas = int(total // 3600)
    minutos = int((total % 3600) // 60)
    segundos = total % 60
    milis = int(round((segundos - int(segundos)) * 1000))
    segundos = int(segundos)
    return f"{horas}:{minutos:02d}:{segundos:02d}.{milis:03d}"

def sanear_infinitos(obj):
    if isinstance(obj, dict):
        return {k: sanear_infinitos(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [sanear_infinitos(v) for v in obj]
    elif isinstance(obj, float) and (obj == float('inf') or obj == float('-inf')):
        return None
    return obj

# ---------- DETECTAR TEMPORADAS ----------
temporadas_raw = []
for carpeta in sorted(os.listdir(CARPETA_BASE)):
    ruta = os.path.join(CARPETA_BASE, carpeta)
    if os.path.isdir(ruta) and any(f.endswith('.json') for f in os.listdir(ruta)):
        temporadas_raw.append(carpeta)

mapeo = {c: nombre_corto(c) for c in temporadas_raw}
temporadas_ordenadas = sorted(mapeo.keys(),
                              key=lambda c: int(c.split('_')[0][1:]) if c.split('_')[0][1:].isdigit() else 0)

# ---------- PROCESAR DATOS ----------
resultados = []
pilotos_por_temp = []
pole_data = []

temp_dict = defaultdict(lambda: {
    "Piloto": "", "Equipo": "", "Temporada": "",
    "Puntos_Carrera": 0, "Puntos_Sprint": 0, "Puntos_Total": 0,
    "Victorias": 0, "Podios": 0, "Poles": 0, "Vueltas_Rápidas": 0,
    "DNF": 0, "Carreras": 0,
    "Suma_Pos_Carrera": 0, "Suma_Grid": 0, "Suma_Remontada": 0,
    "Suma_Pos_Sprint": 0, "Carreras_Sprint": 0,
    "Vueltas_Totales": 0,
    "Posiciones": defaultdict(int),
    "Mejor_Pos": None, "Peor_Pos": None
})

cara_a_cara_temp = defaultdict(lambda: {
    "PilotoA": "", "PilotoB": "", "Temporada": "", "Equipo": "",
    "Clasif_Normal_A": 0, "Clasif_Normal_B": 0,
    "Clasif_Sprint_A": 0, "Clasif_Sprint_B": 0,
    "Carrera_Normal_A": 0, "Carrera_Normal_B": 0,
    "Carrera_Sprint_A": 0, "Carrera_Sprint_B": 0
})

secuencias_piloto = defaultdict(list)
orden_carreras_normal = defaultdict(list)
poles_por_carrera = defaultdict(dict)

# ----- FASE 1: CARGAR TODOS LOS ARCHIVOS Y DETECTAR ÚLTIMA CARRERA NORMAL -----
archivos_por_temporada = defaultdict(list)

for carpeta in temporadas_ordenadas:
    temp_display = mapeo[carpeta]
    ruta_temp = os.path.join(CARPETA_BASE, carpeta)

    archivos_info = []
    for archivo in os.listdir(ruta_temp):
        if archivo.endswith('.json'):
            ruta_archivo = os.path.join(ruta_temp, archivo)
            mtime = os.path.getmtime(ruta_archivo)
            archivos_info.append((archivo, ruta_archivo, mtime))
    archivos_info.sort(key=lambda x: x[2])

    for archivo, ruta_json, mtime in archivos_info:
        with open(ruta_json, 'r', encoding='utf-8') as f:
            datos = json.load(f)
        archivos_por_temporada[temp_display].append({
            'archivo': archivo,
            'ruta_json': ruta_json,
            'mtime': mtime,
            'datos': datos
        })

# Determinar la última carrera normal de cada temporada
ultimo_circuito_por_temp = {}
for temp_display, lista_archivos in archivos_por_temporada.items():
    ultimo_archivo = None
    for item in lista_archivos:
        es_sprint = "sprint" in item['archivo'].lower()
        session = item['datos'].get("SessionType")
        if session == "Race" and not es_sprint:
            ultimo_archivo = item
    if ultimo_archivo:
        ultimo_circuito_por_temp[temp_display] = ultimo_archivo['datos']["TrackName"]

# ----- FASE 2: PROCESAR LOS DATOS CON PUNTOS DOBLES -----
for temp_display, lista_archivos in archivos_por_temporada.items():
    for item in lista_archivos:
        archivo = item['archivo']
        datos = item['datos']

        es_sprint = "sprint" in archivo.lower()
        session = datos.get("SessionType")
        qual = datos.get("QualType")

        if session == "Race":
            tipo = "Sprint" if es_sprint else "Carrera"
            circuito = datos["TrackName"]

            es_ultima_carrera = False
            if tipo == "Carrera":
                if temp_display in ultimo_circuito_por_temp and circuito == ultimo_circuito_por_temp[temp_display]:
                    es_ultima_carrera = True

            if tipo == "Carrera":
                orden_carreras_normal[temp_display].append(circuito)

            equipos_pilotos = defaultdict(list)
            for d in datos["Drivers"]:
                if d["Team"]["Name"].lower() == "frontier racing":
                    continue
                if d["Driver"]["Name"] in PILOTOS_EXCLUIDOS:
                    continue
                equipos_pilotos[d["Team"]["Name"]].append(d)

            for equipo, pilotos in equipos_pilotos.items():
                if len(pilotos) == 2:
                    a, b = sorted(pilotos, key=lambda x: x["Driver"]["Name"])
                    nombreA, nombreB = a["Driver"]["Name"], b["Driver"]["Name"]
                    posA, posB = a["Position"], b["Position"]
                    gridA, gridB = a.get("GridPosition", 0), b.get("GridPosition", 0)
                    ganadorC = "A" if gridA < gridB else ("B" if gridB < gridA else None)
                    ganadorR = "A" if posA < posB else ("B" if posB < posA else None)

                    clave = (nombreA, nombreB, temp_display)
                    entry = cara_a_cara_temp[clave]
                    entry["PilotoA"] = nombreA
                    entry["PilotoB"] = nombreB
                    entry["Temporada"] = temp_display
                    entry["Equipo"] = equipo
                    if tipo == "Carrera":
                        if ganadorC == "A": entry["Clasif_Normal_A"] += 1
                        elif ganadorC == "B": entry["Clasif_Normal_B"] += 1
                        if ganadorR == "A": entry["Carrera_Normal_A"] += 1
                        elif ganadorR == "B": entry["Carrera_Normal_B"] += 1
                    else:
                        if ganadorC == "A": entry["Clasif_Sprint_A"] += 1
                        elif ganadorC == "B": entry["Clasif_Sprint_B"] += 1
                        if ganadorR == "A": entry["Carrera_Sprint_A"] += 1
                        elif ganadorR == "B": entry["Carrera_Sprint_B"] += 1

            for d in datos["Drivers"]:
                if d["Team"]["Name"].lower() == "frontier racing":
                    continue
                if d["Driver"]["Name"] in PILOTOS_EXCLUIDOS:
                    continue

                es_vr = d["Driver"]["Name"] == datos.get("FastestLapDriver", {}).get("Name", "")
                vr_mostrar = "Sí" if (es_vr and tipo == "Carrera") else ""
                estado = d.get("Status", "Ok")

                tiempo_form = formatear_tiempo(d.get("TimeInt", 0))
                resultados.append([
                    temp_display,
                    circuito,
                    tipo,
                    d["Position"],
                    d["Driver"]["Name"],
                    d["Team"]["Name"],
                    d.get("GridPosition", 0) + 1,
                    tiempo_form,
                    d["LapsCount"],
                    estado,
                    vr_mostrar
                ])

                pos = d["Position"]
                grid = d.get("GridPosition", 0)
                puntos = 0
                if tipo == "Carrera":
                    puntos = PUNTOS_CARRERA.get(pos, 0)
                    if es_vr and pos <= 10:
                        puntos += PUNTO_VUELTA_RAPIDA
                    if es_ultima_carrera:
                        puntos *= 2
                else:
                    puntos = PUNTOS_SPRINT.get(pos, 0)

                clave_pil = (d["Driver"]["Name"], temp_display)
                entry_pil = temp_dict[clave_pil]
                entry_pil["Piloto"] = d["Driver"]["Name"]
                entry_pil["Equipo"] = d["Team"]["Name"]
                entry_pil["Temporada"] = temp_display
                if tipo == "Carrera":
                    entry_pil["Puntos_Carrera"] += puntos
                    entry_pil["Carreras"] += 1
                    entry_pil["Suma_Pos_Carrera"] += pos
                    entry_pil["Suma_Grid"] += grid
                    entry_pil["Suma_Remontada"] += (grid - pos)
                    entry_pil["Vueltas_Totales"] += d["LapsCount"]
                    if pos == 1: entry_pil["Victorias"] += 1
                    if pos <= 3: entry_pil["Podios"] += 1
                    if es_vr: entry_pil["Vueltas_Rápidas"] += 1
                    if entry_pil["Mejor_Pos"] is None or pos < entry_pil["Mejor_Pos"]:
                        entry_pil["Mejor_Pos"] = pos
                    if entry_pil["Peor_Pos"] is None or pos > entry_pil["Peor_Pos"]:
                        entry_pil["Peor_Pos"] = pos
                    entry_pil["Posiciones"][pos] += 1
                    secuencias_piloto[(d["Driver"]["Name"], temp_display)].append({
                        "puntos": puntos,
                        "dnf": estado != "Ok",
                        "victoria": pos == 1,
                        "podio": pos <= 3,
                        "pole": None
                    })
                else:
                    entry_pil["Puntos_Sprint"] += puntos
                    entry_pil["Carreras_Sprint"] += 1
                    entry_pil["Suma_Pos_Sprint"] += pos
                entry_pil["Puntos_Total"] += puntos

                if estado != "Ok":
                    entry_pil["DNF"] += 1

        elif session == "Qualification" and qual == "Q3" and not es_sprint:
            poleman = datos["Drivers"][0]["Driver"]["Name"]
            equipo_pole = datos["Drivers"][0]["Team"]["Name"]
            if equipo_pole.lower() == "frontier racing" or poleman in PILOTOS_EXCLUIDOS:
                continue
            circuito = datos["TrackName"]
            pole_data.append([temp_display, circuito, poleman, equipo_pole])
            clave_pole = (poleman, temp_display)
            entry_pole = temp_dict[clave_pole]
            entry_pole["Piloto"] = poleman
            entry_pole["Equipo"] = equipo_pole
            entry_pole["Temporada"] = temp_display
            entry_pole["Poles"] += 1
            poles_por_carrera[(temp_display, circuito)] = poleman

# Asignar poles a las secuencias
for (piloto, temp), sec in secuencias_piloto.items():
    for i, carrera in enumerate(sec):
        circuito = orden_carreras_normal[temp][i] if i < len(orden_carreras_normal[temp]) else None
        if circuito and (temp, circuito) in poles_por_carrera:
            carrera["pole"] = (poles_por_carrera[(temp, circuito)] == piloto)
        else:
            carrera["pole"] = False

pilotos_por_temp = list(temp_dict.values())
for p in pilotos_por_temp:
    p["Posiciones"] = dict(p["Posiciones"])
pilotos_por_temp = sanear_infinitos(pilotos_por_temp)

# Totales pilotos
totales_pilotos = defaultdict(lambda: {
    "Piloto": "", "Equipos": set(),
    "Puntos_Carrera": 0, "Puntos_Sprint": 0, "Puntos_Total": 0,
    "Victorias": 0, "Podios": 0, "Poles": 0, "Vueltas_Rápidas": 0,
    "DNF": 0, "Carreras": 0,
    "Suma_Pos_Carrera": 0, "Suma_Grid": 0, "Suma_Remontada": 0,
    "Vueltas_Totales": 0, "Carreras_Sprint": 0, "Suma_Pos_Sprint": 0,
    "Mejor_Pos": None, "Peor_Pos": None,
    "Posiciones": defaultdict(int)
})
for entry in pilotos_por_temp:
    nombre = entry["Piloto"]
    tot = totales_pilotos[nombre]
    tot["Piloto"] = nombre
    tot["Equipos"].add(entry["Equipo"])
    tot["Puntos_Carrera"] += entry["Puntos_Carrera"]
    tot["Puntos_Sprint"] += entry["Puntos_Sprint"]
    tot["Puntos_Total"] += entry["Puntos_Total"]
    tot["Victorias"] += entry["Victorias"]
    tot["Podios"] += entry["Podios"]
    tot["Poles"] += entry["Poles"]
    tot["Vueltas_Rápidas"] += entry["Vueltas_Rápidas"]
    tot["DNF"] += entry["DNF"]
    tot["Carreras"] += entry["Carreras"]
    tot["Suma_Pos_Carrera"] += entry["Suma_Pos_Carrera"]
    tot["Suma_Grid"] += entry.get("Suma_Grid", 0)
    tot["Suma_Remontada"] += entry.get("Suma_Remontada", 0)
    tot["Vueltas_Totales"] += entry.get("Vueltas_Totales", 0)
    tot["Carreras_Sprint"] += entry.get("Carreras_Sprint", 0)
    tot["Suma_Pos_Sprint"] += entry.get("Suma_Pos_Sprint", 0)
    if entry["Mejor_Pos"] is not None:
        if tot["Mejor_Pos"] is None or entry["Mejor_Pos"] < tot["Mejor_Pos"]:
            tot["Mejor_Pos"] = entry["Mejor_Pos"]
    if entry["Peor_Pos"] is not None:
        if tot["Peor_Pos"] is None or entry["Peor_Pos"] > tot["Peor_Pos"]:
            tot["Peor_Pos"] = entry["Peor_Pos"]
    for pos, count in entry["Posiciones"].items():
        tot["Posiciones"][pos] += count

lista_totales = sorted(totales_pilotos.values(), key=lambda x: -x["Puntos_Total"])
for t in lista_totales:
    t["Equipos"] = ", ".join(sorted(t["Equipos"]))
    t["Posiciones"] = dict(t["Posiciones"])
lista_totales = sanear_infinitos(lista_totales)

pilotos_por_temp.sort(key=lambda x: (x["Temporada"], -x["Puntos_Total"]))

# Constructores
constructores_por_temp = defaultdict(lambda: {
    "Equipo": "", "Temporada": "",
    "Victorias": 0, "Podios": 0, "Poles": 0, "DNF": 0, "Puntos": 0
})
for entry in pilotos_por_temp:
    clave = (entry["Equipo"], entry["Temporada"])
    c = constructores_por_temp[clave]
    c["Equipo"] = entry["Equipo"]
    c["Temporada"] = entry["Temporada"]
    c["Victorias"] += entry["Victorias"]
    c["Podios"] += entry["Podios"]
    c["Poles"] += entry["Poles"]
    c["DNF"] += entry["DNF"]
    c["Puntos"] += entry["Puntos_Total"]

lista_constructores_temp = sorted(constructores_por_temp.values(),
                                  key=lambda x: (x["Temporada"], -x["Puntos"]))

totales_constructores = defaultdict(lambda: {
    "Equipo": "", "Victorias": 0, "Podios": 0, "Poles": 0, "DNF": 0, "Puntos": 0
})
for c in lista_constructores_temp:
    equipo = c["Equipo"]
    tot = totales_constructores[equipo]
    tot["Equipo"] = equipo
    tot["Victorias"] += c["Victorias"]
    tot["Podios"] += c["Podios"]
    tot["Poles"] += c["Poles"]
    tot["DNF"] += c["DNF"]
    tot["Puntos"] += c["Puntos"]

lista_totales_constructores = sorted(totales_constructores.values(), key=lambda x: -x["Puntos"])

# ---------- CARA A CARA ----------
cara_a_cara_lista = list(cara_a_cara_temp.values())
cara_a_cara_lista.sort(key=lambda x: (x["Temporada"], x["Equipo"], x["PilotoA"]))

cara_a_cara_totales = defaultdict(lambda: {
    "PilotoA": "", "PilotoB": "", "Equipos": set(),
    "Clasif_Normal_A": 0, "Clasif_Normal_B": 0,
    "Clasif_Sprint_A": 0, "Clasif_Sprint_B": 0,
    "Carrera_Normal_A": 0, "Carrera_Normal_B": 0,
    "Carrera_Sprint_A": 0, "Carrera_Sprint_B": 0
})
for entry in cara_a_cara_lista:
    clave_cc = (entry["PilotoA"], entry["PilotoB"])
    tot_cc = cara_a_cara_totales[clave_cc]
    tot_cc["PilotoA"] = entry["PilotoA"]
    tot_cc["PilotoB"] = entry["PilotoB"]
    tot_cc["Equipos"].add(entry["Equipo"])
    for campo in ["Clasif_Normal_A", "Clasif_Normal_B", "Clasif_Sprint_A", "Clasif_Sprint_B",
                  "Carrera_Normal_A", "Carrera_Normal_B", "Carrera_Sprint_A", "Carrera_Sprint_B"]:
        tot_cc[campo] += entry[campo]

cara_a_cara_totales_lista = list(cara_a_cara_totales.values())
for t in cara_a_cara_totales_lista:
    t["Equipos"] = ", ".join(sorted(t["Equipos"]))

# ---------- PROMEDIOS ----------
def calc_promedios(entry):
    c = entry["Carreras"]
    spr = entry.get("Carreras_Sprint", 0)
    mejor = entry.get("Mejor_Pos")
    peor = entry.get("Peor_Pos")
    return {
        "Piloto": entry["Piloto"],
        "Equipo": entry.get("Equipo", ""),
        "Temporada": entry.get("Temporada", ""),
        "Carreras": c,
        "Prom_Pos_Carrera": round(entry["Suma_Pos_Carrera"] / c, 2) if c else None,
        "Prom_Grid": round(entry.get("Suma_Grid", 0) / c, 2) if c else None,
        "Prom_Remontada": round(entry.get("Suma_Remontada", 0) / c, 2) if c else None,
        "Pts_por_Carrera": round(entry["Puntos_Carrera"] / c, 2) if c else 0,
        "% Podios": round(entry["Podios"] / c * 100, 1) if c else 0,
        "% Victorias": round(entry["Victorias"] / c * 100, 1) if c else 0,
        "% Poles": round(entry["Poles"] / c * 100, 1) if c else 0,
        "Vueltas_Totales": entry.get("Vueltas_Totales", 0),
        "Mejor_Pos": mejor,
        "Peor_Pos": peor,
        "Prom_Pos_Sprint": round(entry.get("Suma_Pos_Sprint", 0) / spr, 2) if spr else None,
    }

promedios_temp = [calc_promedios(p) for p in pilotos_por_temp]
promedios_totales = [calc_promedios(t) for t in lista_totales]
promedios_temp = sanear_infinitos(promedios_temp)
promedios_totales = sanear_infinitos(promedios_totales)

# ---------- RACHAS ----------
def calcular_racha_maxima(secuencia, campo_condicion):
    max_racha = 0
    racha_actual = 0
    for item in secuencia:
        if campo_condicion(item):
            racha_actual += 1
            if racha_actual > max_racha:
                max_racha = racha_actual
        else:
            racha_actual = 0
    return max_racha

rachas_temp = {}
for (piloto, temp), sec in secuencias_piloto.items():
    rachas_temp[(piloto, temp)] = {
        "Piloto": piloto,
        "Temporada": temp,
        "Racha Puntos": calcular_racha_maxima(sec, lambda x: x["puntos"] > 0),
        "Racha sin puntos": calcular_racha_maxima(sec, lambda x: x["puntos"] == 0),
        "Racha Sin DNF": calcular_racha_maxima(sec, lambda x: not x["dnf"]),
        "Racha con DNF": calcular_racha_maxima(sec, lambda x: x["dnf"]),
        "Racha Podios": calcular_racha_maxima(sec, lambda x: x["podio"]),
        "Racha Victorias": calcular_racha_maxima(sec, lambda x: x["victoria"]),
        "Racha Poles": calcular_racha_maxima(sec, lambda x: x["pole"]),
    }

rachas_totales = {}
for (piloto, temp), r in rachas_temp.items():
    if piloto not in rachas_totales:
        rachas_totales[piloto] = {
            "Piloto": piloto,
            "Racha Puntos": 0,
            "Racha sin puntos": 0,
            "Racha Sin DNF": 0,
            "Racha con DNF": 0,
            "Racha Podios": 0,
            "Racha Victorias": 0,
            "Racha Poles": 0,
        }
    for campo in rachas_totales[piloto]:
        if r[campo] > rachas_totales[piloto][campo]:
            rachas_totales[piloto][campo] = r[campo]

rachas_temp_list = list(rachas_temp.values())
rachas_totales_list = list(rachas_totales.values())

# ---------- EVOLUCIÓN DE PUNTOS ----------
evolucion_puntos = defaultdict(dict)
for temp in mapeo.values():
    pilotos_en_temp = set()
    for (piloto, t) in secuencias_piloto:
        if t == temp:
            pilotos_en_temp.add(piloto)
    for piloto in pilotos_en_temp:
        sec = secuencias_piloto[(piloto, temp)]
        acum = 0
        acumulados = []
        for carrera in sec:
            acum += carrera["puntos"]
            acumulados.append(acum)
        evolucion_puntos[temp][piloto] = acumulados

# ---------- RÉCORDS ----------
def get_top(campo, n=5):
    return sorted([p for p in lista_totales if p[campo] > 0], key=lambda x: -x[campo])[:n]

records = {
    "Puntos": [(p["Piloto"], p["Puntos_Total"]) for p in get_top("Puntos_Total")],
    "Victorias": [(p["Piloto"], p["Victorias"]) for p in get_top("Victorias")],
    "Podios": [(p["Piloto"], p["Podios"]) for p in get_top("Podios")],
    "Poles": [(p["Piloto"], p["Poles"]) for p in get_top("Poles")],
    "Vueltas Rápidas": [(p["Piloto"], p["Vueltas_Rápidas"]) for p in get_top("Vueltas_Rápidas")],
    "Carreras": [(p["Piloto"], p["Carreras"]) for p in get_top("Carreras")],
    "DNF": [(p["Piloto"], p["DNF"]) for p in get_top("DNF")],
}

# ---------- GENERAR HTML ----------
html = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<title>Estadísticas Liga F1 Manager</title>
<style>
  body {{ font-family: 'Segoe UI', sans-serif; margin: 20px; background: #f4f4f4; color: #333; }}
  h1 {{ text-align: center; }}
  .tabs {{ display: flex; justify-content: center; margin-bottom: 20px; flex-wrap: wrap; }}
  .tabs button {{ background: #ddd; border: none; padding: 10px 15px; margin: 0 3px; cursor: pointer; font-weight: bold; border-radius: 5px; }}
  .tabs button.active {{ background: #0066cc; color: white; }}
  .tab-content {{ display: none; }}
  .tab-content.active {{ display: block; }}
  table {{ border-collapse: collapse; width: 100%; margin-bottom: 30px; background: white; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
  th, td {{ padding: 8px 10px; border: 1px solid #ccc; text-align: center; }}
  th {{ background: #0066cc; color: white; position: sticky; top: 0; cursor: pointer; user-select: none; }}
  th:hover {{ background: #0055aa; }}
  th.sort-asc::after {{ content: ' ↑'; }}
  th.sort-desc::after {{ content: ' ↓'; }}
  tr:nth-child(even) {{ background: #f9f9f9; }}
  .filtros {{ text-align: center; margin-bottom: 10px; }}
  .filtros select {{ padding: 8px; font-size: 16px; margin: 0 5px; }}
  .mensaje {{ font-style: italic; text-align: center; margin: 20px; }}
  .col-equipos {{ max-width: 180px; word-wrap: break-word; white-space: normal; font-size: 0.85em; }}
</style>
</head>
<body>
<h1>🏎️ Estadísticas Liga F1 Manager</h1>

<div class="tabs">
  <button class="tab-link active" onclick="openTab(event,'pilotos')">Pilotos</button>
  <button class="tab-link" onclick="openTab(event,'constructores')">Constructores</button>
  <button class="tab-link" onclick="openTab(event,'resultados')">Resultados</button>
  <button class="tab-link" onclick="openTab(event,'promedios')">Promedios</button>
  <button class="tab-link" onclick="openTab(event,'mapa')">Mapa Pos.</button>
  <button class="tab-link" onclick="openTab(event,'caraacara')">Cara a Cara</button>
  <button class="tab-link" onclick="openTab(event,'poles')">Poles</button>
  <button class="tab-link" onclick="openTab(event,'records')">Récords</button>
  <button class="tab-link" onclick="openTab(event,'rachas')">Rachas</button>
  <button class="tab-link" onclick="openTab(event,'evolucion')">Evolución</button>
</div>

<div class="filtros">
  <label for="filtroTemp">Temporada:</label>
  <select id="filtroTemp" onchange="cambioTemporada()">
    <option value="todas">Todas</option>
"""

for carpeta in temporadas_ordenadas:
    display = mapeo[carpeta]
    html += f'    <option value="{display}">{display}</option>\n'

html += """  </select>
</div>

<!-- PESTAÑAS -->
<div id="pilotos" class="tab-content active"><h2>Clasificación de Pilotos</h2><span id="tabla-pilotos"></span></div>
<div id="constructores" class="tab-content"><h2>Clasificación de Constructores</h2><span id="tabla-constructores"></span></div>
<div id="resultados" class="tab-content">
  <h2>Resultados por Carrera</h2>
  <div class="filtros">
    <label for="filtroCircuito">Circuito:</label>
    <select id="filtroCircuito" onchange="filtrarResultados()">
      <option value="todos">Todos</option>
    </select>
    <label for="filtroTipo">Tipo:</label>
    <select id="filtroTipo" onchange="filtrarResultados()">
      <option value="todos">Todos</option>
      <option value="Carrera">Carrera</option>
      <option value="Sprint">Sprint</option>
    </select>
  </div>
  <span id="tabla-resultados"></span>
</div>
<div id="promedios" class="tab-content"><h2>Promedios y Rendimiento</h2><span id="tabla-promedios"></span></div>
<div id="mapa" class="tab-content"><h2>Mapa de Posiciones (carreras normales)</h2><span id="tabla-mapa"></span></div>
<div id="caraacara" class="tab-content"><h2>Cara a Cara entre compañeros</h2><span id="tabla-caraacara"></span></div>
<div id="poles" class="tab-content"><h2>Pole Positions</h2><span id="tabla-poles"></span></div>
<div id="records" class="tab-content"><h2>Récords Históricos (Top 5)</h2><span id="tabla-records"></span></div>
<div id="rachas" class="tab-content"><h2>Rachas</h2><span id="tabla-rachas"></span></div>
<div id="evolucion" class="tab-content"><h2>Evolución de Puntos por Carrera</h2><span id="tabla-evolucion"></span></div>

<script>
const totalesPilotos = """ + json.dumps(lista_totales) + """;
const pilotosPorTemp = """ + json.dumps(pilotos_por_temp) + """;
const constructoresTempData = """ + json.dumps(lista_constructores_temp) + """;
const totalesConstructores = """ + json.dumps(lista_totales_constructores) + """;
const resultadosData = """ + json.dumps(resultados) + """;
const polesData = """ + json.dumps(pole_data) + """;
const caraACaraTemp = """ + json.dumps(cara_a_cara_lista) + """;
const caraACaraTotales = """ + json.dumps(cara_a_cara_totales_lista) + """;
const promediosTemp = """ + json.dumps(promedios_temp) + """;
const promediosTotales = """ + json.dumps(promedios_totales) + """;
const records = """ + json.dumps(records) + """;
const rachasTemp = """ + json.dumps(rachas_temp_list) + """;
const rachasTotales = """ + json.dumps(rachas_totales_list) + """;
const evolucionData = """ + json.dumps(evolucion_puntos) + """;

const cabPilotosTotales = ["Piloto","Equipos","Carreras","Puntos_Total","Victorias","Podios","Poles","Vueltas_Rápidas","DNF"];
const cabPilotosTemp = ["Piloto","Equipo","Temporada","Carreras","Puntos_Carrera","Puntos_Sprint","Puntos_Total","Victorias","Podios","Poles","Vueltas_Rápidas","DNF"];
const cabConstructoresTemp = ["Equipo","Temporada","Victorias","Podios","Poles","DNF","Puntos"];
const cabConstructoresTotales = ["Equipo","Victorias","Podios","Poles","DNF","Puntos"];
const cabResultados = ["Temporada","Circuito","Tipo","Posición","Piloto","Equipo","Grid","Tiempo","Vueltas","Estado","VR"];
const cabPoles = ["Temporada","Circuito","Piloto","Equipo"];
const cabCaraACaraTemp = ["Temporada","Equipo","Piloto A","Piloto B","Clasif. Normal","Clasif. Sprint","Carrera Normal","Carrera Sprint","Total"];
const cabCaraACaraTotales = ["Piloto A","Piloto B","Equipos","Clasif. Normal","Clasif. Sprint","Carrera Normal","Carrera Sprint","Total"];
const cabPromediosTemp = ["Piloto","Equipo","Temporada","Carreras","Prom_Pos_Carrera","Prom_Grid","Prom_Remontada","Pts_por_Carrera","% Podios","% Victorias","% Poles","Vueltas_Totales","Mejor_Pos","Peor_Pos","Prom_Pos_Sprint"];
const cabPromediosTotales = ["Piloto","Equipos","Carreras","Prom_Pos_Carrera","Prom_Grid","Prom_Remontada","Pts_por_Carrera","% Podios","% Victorias","% Poles","Vueltas_Totales","Mejor_Pos","Peor_Pos","Prom_Pos_Sprint"];
const cabRecords = ["Categoría","1º","2º","3º","4º","5º"];
const cabRachasTemp = ["Piloto","Temporada","Racha Puntos","Racha sin puntos","Racha Sin DNF","Racha con DNF","Racha Podios","Racha Victorias","Racha Poles"];
const cabRachasTotales = ["Piloto","Racha Puntos","Racha sin puntos","Racha Sin DNF","Racha con DNF","Racha Podios","Racha Victorias","Racha Poles"];

const sortStates = {};

function crearTabla(headers, datos, sortInfo = null) {
  let html = '<table><thead><tr>';
  headers.forEach((h, idx) => {
    let clase = '';
    if (sortInfo && idx === sortInfo.col) {
      clase = sortInfo.dir === 1 ? 'sort-asc' : 'sort-desc';
    }
    html += `<th class="${clase}" data-col="${idx}">${h}</th>`;
  });
  html += '</tr></thead><tbody>';
  if (datos.length === 0) {
    html += '<tr><td colspan="' + headers.length + '">Sin datos</td></tr>';
  } else {
    datos.forEach(fila => {
      html += '<tr>';
      if (Array.isArray(fila)) {
        fila.forEach((celda, idx) => {
          let claseCelda = '';
          if (headers[idx] === 'Equipos' || headers[idx] === 'Equipo') {
            claseCelda = ' class="col-equipos"';
          }
          html += `<td${claseCelda}>${celda != null ? celda : ''}</td>`;
        });
      } else {
        headers.forEach(h => {
          let claseCelda = '';
          if (h === 'Equipos' || h === 'Equipo') {
            claseCelda = ' class="col-equipos"';
          }
          html += `<td${claseCelda}>${fila[h] != null ? fila[h] : ''}</td>`;
        });
      }
      html += '</tr>';
    });
  }
  html += '</tbody></table>';
  return html;
}

function hacerOrdenable(containerId, headers, dataArray, sortKey) {
  if (!sortStates[sortKey]) sortStates[sortKey] = { col: null, dir: -1 };
  const state = sortStates[sortKey];
  const container = document.getElementById(containerId);
  container.innerHTML = crearTabla(headers, dataArray, state);

  container.querySelectorAll('th').forEach(th => {
    th.onclick = () => {
      const colIdx = parseInt(th.dataset.col);
      const campo = headers[colIdx];
      if (state.col === colIdx) {
        state.dir *= -1;
      } else {
        state.col = colIdx;
        state.dir = -1;
      }
      dataArray.sort((a, b) => {
        let va = Array.isArray(a) ? a[colIdx] : a[campo];
        let vb = Array.isArray(b) ? b[colIdx] : b[campo];
        if (va == null) va = '';
        if (vb == null) vb = '';
        if (typeof va === 'string' && !isNaN(va) && va !== '') va = parseFloat(va);
        if (typeof vb === 'string' && !isNaN(vb) && vb !== '') vb = parseFloat(vb);
        if (va < vb) return -1 * state.dir;
        if (va > vb) return 1 * state.dir;
        return 0;
      });
      hacerOrdenable(containerId, headers, dataArray, sortKey);
    };
  });
}

function actualizarPilotos(temp) {
  let dat, cab;
  if (temp === 'todas') {
    dat = totalesPilotos.slice();
    cab = cabPilotosTotales;
  } else {
    dat = pilotosPorTemp.filter(p => p.Temporada === temp);
    cab = cabPilotosTemp;
  }
  hacerOrdenable('tabla-pilotos', cab, dat, 'pilotos');
}

function actualizarConstructores(temp) {
  let dat, cab;
  if (temp === 'todas') {
    dat = totalesConstructores.slice();
    cab = cabConstructoresTotales;
  } else {
    dat = constructoresTempData.filter(c => c.Temporada === temp);
    cab = cabConstructoresTemp;
  }
  hacerOrdenable('tabla-constructores', cab, dat, 'constructores');
}

function actualizarPromedios(temp) {
  let dat, cab;
  if (temp === 'todas') {
    dat = promediosTotales.slice();
    cab = cabPromediosTotales;
  } else {
    dat = promediosTemp.filter(p => p.Temporada === temp);
    cab = cabPromediosTemp;
  }
  hacerOrdenable('tabla-promedios', cab, dat, 'promedios');
}

function actualizarMapa(temp) {
  let maxGlobal = 22;
  let cab, filas;
  if (temp === 'todas') {
    const pilotos = totalesPilotos.slice();
    pilotos.forEach(p => {
      Object.keys(p.Posiciones).forEach(k => {
        const pos = parseInt(k);
        if (pos > maxGlobal) maxGlobal = pos;
      });
    });
    cab = ["Piloto"];
    for (let i=1; i<=maxGlobal; i++) cab.push(i.toString());
    filas = pilotos.map(p => {
      const row = [p.Piloto];
      for (let i=1; i<=maxGlobal; i++) {
        row.push((p.Posiciones && p.Posiciones[i.toString()]) ? p.Posiciones[i.toString()] : 0);
      }
      return row;
    });
  } else {
    const pilotos = pilotosPorTemp.filter(p => p.Temporada === temp);
    pilotos.forEach(p => {
      Object.keys(p.Posiciones).forEach(k => {
        const pos = parseInt(k);
        if (pos > maxGlobal) maxGlobal = pos;
      });
    });
    cab = ["Piloto","Temporada"];
    for (let i=1; i<=maxGlobal; i++) cab.push(i.toString());
    filas = pilotos.map(p => {
      const row = [p.Piloto, p.Temporada];
      for (let i=1; i<=maxGlobal; i++) {
        row.push((p.Posiciones && p.Posiciones[i.toString()]) ? p.Posiciones[i.toString()] : 0);
      }
      return row;
    });
  }
  document.getElementById('tabla-mapa').innerHTML = crearTabla(cab, filas);
}

function actualizarRecords() {
  const categories = Object.keys(records);
  let filas = categories.map(cat => {
    const row = [cat];
    for (let i=0; i<5; i++) {
      const entry = records[cat][i];
      row.push(entry ? `${entry[0]} (${entry[1]})` : '');
    }
    return row;
  });
  document.getElementById('tabla-records').innerHTML = crearTabla(cabRecords, filas);
}

function formatearCaraACara(entry, incluirTemp = true) {
  let totalA = entry.Clasif_Normal_A + entry.Clasif_Sprint_A + entry.Carrera_Normal_A + entry.Carrera_Sprint_A;
  let totalB = entry.Clasif_Normal_B + entry.Clasif_Sprint_B + entry.Carrera_Normal_B + entry.Carrera_Sprint_B;
  let fila = [];
  if (incluirTemp) {
    fila.push(entry.Temporada, entry.Equipo, entry.PilotoA, entry.PilotoB);
  } else {
    fila.push(entry.PilotoA, entry.PilotoB, entry.Equipos);
  }
  fila.push(
    `${entry.Clasif_Normal_A} – ${entry.Clasif_Normal_B}`,
    `${entry.Clasif_Sprint_A} – ${entry.Clasif_Sprint_B}`,
    `${entry.Carrera_Normal_A} – ${entry.Carrera_Normal_B}`,
    `${entry.Carrera_Sprint_A} – ${entry.Carrera_Sprint_B}`,
    `${totalA} – ${totalB}`
  );
  return fila;
}

function actualizarCaraACara(temp) {
  let datos, cab, incluirTemp;
  if (temp === 'todas') {
    datos = caraACaraTotales;
    cab = cabCaraACaraTotales;
    incluirTemp = false;
  } else {
    datos = caraACaraTemp.filter(e => e.Temporada === temp);
    cab = cabCaraACaraTemp;
    incluirTemp = true;
  }
  let filas = datos.map(e => formatearCaraACara(e, incluirTemp));
  hacerOrdenable('tabla-caraacara', cab, filas, 'caraacara');
}

function actualizarPoles(temp) {
  let dat = polesData;
  if (temp !== 'todas') dat = polesData.filter(fila => fila[0] === temp);
  hacerOrdenable('tabla-poles', cabPoles, dat, 'poles');
}

function actualizarRachas(temp) {
  let dat, cab;
  if (temp === 'todas') {
    dat = rachasTotales.slice();
    cab = cabRachasTotales;
  } else {
    dat = rachasTemp.filter(r => r.Temporada === temp);
    cab = cabRachasTemp;
  }
  if (dat.length === 0) {
    document.getElementById('tabla-rachas').innerHTML = '<p class="mensaje">No hay datos de rachas para esta vista.</p>';
    return;
  }
  hacerOrdenable('tabla-rachas', cab, dat, 'rachas');
}

function actualizarEvolucion(temp) {
  const container = document.getElementById('tabla-evolucion');
  if (temp === 'todas') {
    container.innerHTML = '<p class="mensaje">Selecciona una temporada específica para ver la evolución de puntos.</p>';
    return;
  }
  const evol = evolucionData[temp];
  if (!evol || Object.keys(evol).length === 0) {
    container.innerHTML = '<p class="mensaje">No hay datos de evolución para esta temporada.</p>';
    return;
  }
  const pilotos = Object.keys(evol).sort();
  const numCarreras = evol[pilotos[0]].length;
  const cab = ["Piloto"];
  for (let i=1; i<=numCarreras; i++) cab.push(`Carrera ${i}`);
  const filas = pilotos.map(piloto => {
    const row = [piloto];
    evol[piloto].forEach(puntos => row.push(puntos));
    return row;
  });
  hacerOrdenable('tabla-evolucion', cab, filas, 'evolucion');
}

function actualizarSelectorCircuito() {
  const temp = document.getElementById('filtroTemp').value;
  const circSelect = document.getElementById('filtroCircuito');
  const circuitos = new Set();
  resultadosData.forEach(fila => {
    if (temp === 'todas' || fila[0] === temp) circuitos.add(fila[1]);
  });
  const actual = circSelect.value;
  circSelect.innerHTML = '<option value="todos">Todos</option>';
  Array.from(circuitos).sort().forEach(circ => {
    const opt = document.createElement('option');
    opt.value = circ;
    opt.textContent = circ;
    circSelect.appendChild(opt);
  });
  if (Array.from(circSelect.options).some(opt => opt.value === actual)) circSelect.value = actual;
}

function filtrarResultados() {
  const temp = document.getElementById('filtroTemp').value;
  const circ = document.getElementById('filtroCircuito').value;
  const tipo = document.getElementById('filtroTipo').value;
  let datos = resultadosData;
  if (temp !== 'todas') datos = datos.filter(fila => fila[0] === temp);
  if (circ !== 'todos') datos = datos.filter(fila => fila[1] === circ);
  if (tipo !== 'todos') datos = datos.filter(fila => fila[2] === tipo);
  hacerOrdenable('tabla-resultados', cabResultados, datos, 'resultados');
}

function cambioTemporada() {
  const temp = document.getElementById('filtroTemp').value;
  actualizarPilotos(temp);
  actualizarConstructores(temp);
  actualizarPromedios(temp);
  actualizarMapa(temp);
  actualizarCaraACara(temp);
  actualizarPoles(temp);
  actualizarRachas(temp);
  actualizarEvolucion(temp);
  actualizarSelectorCircuito();
  filtrarResultados();
}

function openTab(evt, tabId) {
  document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
  document.querySelectorAll('.tab-link').forEach(el => el.classList.remove('active'));
  document.getElementById(tabId).classList.add('active');
  evt.currentTarget.classList.add('active');
  if (tabId === 'resultados') {
    actualizarSelectorCircuito();
    filtrarResultados();
  }
}

window.onload = function() {
  cambioTemporada();
  actualizarRecords();
};
</script>
</body>
</html>"""

ruta_html = os.path.join(CARPETA_BASE, "Reporte_Liga.html")
with open(ruta_html, 'w', encoding='utf-8') as f:
    f.write(html)

print(f"✅ Reporte generado: {ruta_html}")
webbrowser.open(f"file:///{ruta_html.replace(os.sep, '/')}")