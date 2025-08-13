

import numpy as np
import math
import time

# --- PARÁMETROS POR DEFECTO ---
default_params = {
    "TRENES_OPERATIVOS_REQUERIDOS": 18,
    "NIVEL_SERVICIO_DESEADO": 0.995,
    "FORMA_K_FALLA": 1.5, "DISPONIBILIDAD": 0.93,
    "FORMA_BETA_REPARACION_DISCRETA": 3, "REPARACION_MEDIA": 2,
    "FORMA_BETA_MNT_DISCRETA": 4, "MNT_MEDIO": 1,
    "NUM_SIMULACIONES": 1000, "DIAS_POR_SIMULACION": 365,
    "REQUISITOS_TRENES_HORA": [
        0, 0, 0, 0, 0, 10, 12, 15, 15, 15, 10, 10, 10, 10, 10, 10, 15, 15, 15, 12, 12, 10, 10, 0
    ]
}


# --- FUNCIONES BÁSICAS DE SIMULACIÓN ---
def sample_discrete_weibull(beta, eta, size=1):
    q = math.exp(-(1.0 / eta) ** beta);
    u = np.random.rand(size)
    return np.ceil((np.log(1 - u) / np.log(q)) ** (1.0 / beta)).astype(int)


def weibull_hazard_rate(t, k, lam):
    if t <= 0: return 0
    return (k / lam) * (t / lam) ** (k - 1)


def ejecutar_simulacion_unitaria(trenes_reserva, params, stop_event):

    horas_con_servicio_fallido_total = 0;
    flota_total = params["TRENES_OPERATIVOS_REQUERIDOS"] + trenes_reserva;
    tasa_fallo = 1 - params["DISPONIBILIDAD"];
    mttf_falla = round(1 / tasa_fallo, 2);
    escala_lambda_falla = mttf_falla / math.gamma(1 + 1 / params["FORMA_K_FALLA"]);
    escala_eta_reparacion = params["REPARACION_MEDIA"] / math.gamma(1 + 1 / params["FORMA_BETA_REPARACION_DISCRETA"]);
    escala_eta_mnt = params["MNT_MEDIO"] / math.gamma(1 + 1 / params["FORMA_BETA_MNT_DISCRETA"])
    for sim_num in range(params["NUM_SIMULACIONES"]):
        if stop_event.is_set(): return None
        dias_reparacion_restantes = np.zeros(flota_total, dtype=int);
        dias_mantenimiento_restantes = np.zeros(flota_total, dtype=int);
        dias_desde_ultima_falla = np.zeros(flota_total, dtype=int)
        for dia in range(params["DIAS_POR_SIMULACION"]):
            dias_reparacion_restantes[dias_reparacion_restantes > 0] -= 1;
            dias_mantenimiento_restantes[dias_mantenimiento_restantes > 0] -= 1;
            idx_reparados_hoy = np.where(dias_reparacion_restantes == 0);
            dias_desde_ultima_falla[idx_reparados_hoy] = 0;
            disponibles_inicio_dia_idx = \
            np.where((dias_reparacion_restantes == 0) & (dias_mantenimiento_restantes == 0))[0];
            num_a_mnt = np.random.choice(params["LISTA_MNT"], p=params["P_MNT"]);
            num_a_mnt = min(num_a_mnt, len(disponibles_inicio_dia_idx))
            if num_a_mnt > 0:
                trenes_a_mnt_idx = np.random.choice(disponibles_inicio_dia_idx, size=num_a_mnt, replace=False);
                tiempos_mnt = sample_discrete_weibull(params["FORMA_BETA_MNT_DISCRETA"], escala_eta_mnt,
                                                      size=num_a_mnt);
                dias_mantenimiento_restantes[trenes_a_mnt_idx] = tiempos_mnt
            operativos_idx = np.where((dias_reparacion_restantes == 0) & (dias_mantenimiento_restantes == 0))[0]
            if len(operativos_idx) > 0: dias_desde_ultima_falla[operativos_idx] += 1
            for i in operativos_idx:
                edad_tren = dias_desde_ultima_falla[i];
                prob_falla_tren = weibull_hazard_rate(edad_tren, params["FORMA_K_FALLA"], escala_lambda_falla)
                if np.random.rand() < prob_falla_tren:
                    tiempo_reparacion = \
                    sample_discrete_weibull(params["FORMA_BETA_REPARACION_DISCRETA"], escala_eta_reparacion, size=1)[0];
                    dias_reparacion_restantes[i] = tiempo_reparacion
            trenes_disponibles_hoy = len(
                np.where((dias_reparacion_restantes == 0) & (dias_mantenimiento_restantes == 0))[0])
            for hora in range(24):
                if trenes_disponibles_hoy < params["REQUISITOS_TRENES_HORA"][
                    hora]: horas_con_servicio_fallido_total += 1
    total_horas_simuladas = params["NUM_SIMULACIONES"] * params["DIAS_POR_SIMULACION"] * 24
    if total_horas_simuladas == 0: return 1.0
    if horas_con_servicio_fallido_total == 0: return 1.0
    return 1 - (horas_con_servicio_fallido_total / total_horas_simuladas)


def get_discrete_weibull_pmf(x_range, beta, eta):
    q = math.exp(-(1.0 / eta) ** beta)
    return [q ** ((k - 1) ** beta) - q ** (k ** beta) for k in x_range]


# --- FUNCIÓN PRINCIPAL DE ANÁLISIS ---
def run_full_analysis(params, stop_event, progress_callback=None):
    log_text = f"Iniciando búsqueda de flota...\n"
    log_text += f"1º Objetivo: Encontrar la flota mínima para un servicio >= {params['NIVEL_SERVICIO_DESEADO']:.2%}\n"
    log_text += f"2º Objetivo: Continuar hasta encontrar una flota 'perfecta' (3x 100% seguidos)\n"
    log_text += "-" * 80 + "\n"
    log_text += "{:<15} | {:<16} | {:<12} | {}\n".format("Trenes Reserva", "Nivel Servicio", "Tiempo (s)", "Comentario")
    log_text += "-" * 80 + "\n"

    n_reserva = 0
    flota_minima_requerida = -1
    consecutive_100_percent_count = 0
    history = []

    while True:
        if stop_event.is_set():
            log_text += "\nSimulación detenida por el usuario.\n"
            return {"log_text": log_text, "stopped": True, "plot_history": history,
                    "trenes_optimos": flota_minima_requerida}

        start_time = time.time()
        nivel = ejecutar_simulacion_unitaria(n_reserva, params, stop_event)
        duration = time.time() - start_time

        if nivel is None:
            return {"log_text": log_text, "stopped": True, "history": history, "trenes_optimos": flota_minima_requerida}

        history.append((n_reserva, nivel))

        comment = ""
        if nivel >= params["NIVEL_SERVICIO_DESEADO"]:
            # Se cumple el objetivo mínimo
            if flota_minima_requerida == -1:
                flota_minima_requerida = n_reserva
                comment = f"¡OBJETIVO MÍNIMO ALCANZADO! ({n_reserva} trenes). Buscando perfección..."

            # Independientemente de si es el primero o no, se busca la racha de 100%
            if nivel >= 1.0:
                consecutive_100_percent_count += 1
                if not comment: comment = f"¡100% ALCANZADO! Racha: {consecutive_100_percent_count}/3."
            else:
                consecutive_100_percent_count = 0
                if not comment: comment = "Estable, pero no 100%. Racha reiniciada."
        else:
            # Fallo crítico, no se alcanzó el objetivo
            comment = "Buscando... no alcanza el objetivo."
            flota_minima_requerida = -1  # Se resetea si una flota superior falla
            consecutive_100_percent_count = 0

        log_text += "{:<15} | {:<16.4%} | {:<12.2f} | {}\n".format(n_reserva, nivel, duration, comment)

        if progress_callback:
            progress_callback(log_text, history)

        if consecutive_100_percent_count >= 3:
            flota_perfecta = n_reserva
            break  # Búsqueda de perfección finalizada

        n_reserva += 1

    log_text += "-" * 80 + "\n"
    if flota_minima_requerida != -1:
        log_text += f"\n✅ Flota Mínima Requerida: {flota_minima_requerida} trenes de reserva.\n"
        log_text += f"   (Se encontró una flota 'perfecta' con {flota_perfecta} trenes para referencia).\n"
    else:
        log_text += "\n⚠️ No se encontró una flota que cumpliera el objetivo mínimo en el rango simulado.\n"

    # Preparar datos para gráficos
    tasa_fallo = 1 - params["DISPONIBILIDAD"];
    mttf_falla = round(1 / tasa_fallo, 2);
    escala_eta_reparacion = params["REPARACION_MEDIA"] / math.gamma(1 + 1 / params["FORMA_BETA_REPARACION_DISCRETA"]);
    escala_eta_mnt = params["MNT_MEDIO"] / math.gamma(1 + 1 / params["FORMA_BETA_MNT_DISCRETA"]);
    escala_lambda_falla = mttf_falla / math.gamma(1 + 1 / params["FORMA_K_FALLA"]);
    x_range = np.arange(1, 11);
    pmf_reparacion = get_discrete_weibull_pmf(x_range, params["FORMA_BETA_REPARACION_DISCRETA"], escala_eta_reparacion);
    pmf_mnt = get_discrete_weibull_pmf(x_range, params["FORMA_BETA_MNT_DISCRETA"], escala_eta_mnt);
    edades = np.arange(1, 31);
    tasas_de_falla = [weibull_hazard_rate(t, params["FORMA_K_FALLA"], escala_lambda_falla) for t in edades]
    results = {
        "log_text": log_text, "stopped": False,
        "trenes_optimos": flota_minima_requerida,  # ✅ El valor óptimo reportado es la flota mínima
        "plot_history": history,
        "plot_reparacion": {"x": x_range, "y": pmf_reparacion, "beta": params["FORMA_BETA_REPARACION_DISCRETA"],
                            "eta": escala_eta_reparacion},
        "plot_mnt": {"x": x_range, "y": pmf_mnt, "beta": params["FORMA_BETA_MNT_DISCRETA"], "eta": escala_eta_mnt},
        "plot_falla": {"x": edades, "y": tasas_de_falla, "mttf": mttf_falla},
    }
    return results