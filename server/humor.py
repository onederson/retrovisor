import math


def nivel(total_concluidas: int) -> int:
    return 1 + math.floor(math.sqrt(max(0, total_concluidas) / 5.0))


def calcular(
    hora: int,
    min_sem_toque: float,
    min_sem_claude: float,
    concluidas_hoje: int,
    carinhos_hoje: int,
    uso_5h_pct: float | None,
    gpu_temp: float | None,
) -> dict:
    extras: list[str] = []
    if uso_5h_pct is not None and uso_5h_pct >= 80:
        extras.append("cansado")
    if gpu_temp is not None and gpu_temp >= 80:
        extras.append("calor")

    if 9 <= hora <= 17:
        energia = 1.0
    elif 18 <= hora <= 22:
        energia = 0.6
    elif hora >= 23 or hora <= 5:
        energia = 0.25
    elif 6 <= hora <= 8:
        energia = 0.5
    else:
        energia = 1.0

    if "cansado" in extras:
        energia -= 0.2
    energia = round(max(0.0, energia), 2)

    alegria = min(1.0, 0.4 + 0.05 * concluidas_hoje + 0.1 * carinhos_hoje)
    if min_sem_toque > 240 and min_sem_claude > 240:
        alegria -= 0.3
    alegria = round(max(0.0, alegria), 2)

    if hora >= 23 or hora < 6:
        estado = "sonolento"
        motivo = "é madrugada, tô com sono"
    elif min_sem_toque > 240 and min_sem_claude > 240:
        estado = "carente"
        motivo = "faz tempo que você não aparece"
    elif concluidas_hoje >= 10:
        estado = "animado"
        motivo = f"dia produtivo: {concluidas_hoje} tarefas"
    elif carinhos_hoje >= 5:
        estado = "animado"
        motivo = "ganhei muito carinho hoje"
    elif min_sem_claude < 30:
        estado = "curioso"
        motivo = "tem coisa acontecendo"
    else:
        estado = "tranquilo"
        motivo = "tudo calmo"

    return {
        "estado": estado,
        "energia": float(energia),
        "alegria": float(alegria),
        "extras": extras,
        "motivo": motivo,
    }
