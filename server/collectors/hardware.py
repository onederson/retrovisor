import ctypes
import ctypes.wintypes
import subprocess
import time
import psutil

try:
    import pynvml
except ImportError:
    pynvml = None

NVML_CLOCK_GRAPHICS = getattr(pynvml, "NVML_CLOCK_GRAPHICS", 0) if pynvml else 0
NVML_CLOCK_MEM = getattr(pynvml, "NVML_CLOCK_MEM", 2) if pynvml else 2
NVML_TEMPERATURE_GPU = getattr(pynvml, "NVML_TEMPERATURE_GPU", 0) if pynvml else 0
NVML_PCIE_UTIL_TX_BYTES = getattr(pynvml, "NVML_PCIE_UTIL_TX_BYTES", 0) if pynvml else 0
NVML_PCIE_UTIL_RX_BYTES = getattr(pynvml, "NVML_PCIE_UTIL_RX_BYTES", 1) if pynvml else 1
NVML_TEMPERATURE_THRESHOLD_SLOWDOWN = (
    getattr(pynvml, "NVML_TEMPERATURE_THRESHOLD_SLOWDOWN", 1) if pynvml else 1
)

THROTTLE_MAP = [
    (0x4, "power"),
    (0x8, "hw_slowdown"),
    (0x10, "sync_boost"),
    (0x2, "app_clock"),
    (0x20, "termico"),
    (0x40, "termico"),
    (0x80, "potencia_hw"),
    (0x100, "display"),
]


def _parse_throttle(reasons: int | None) -> list[str]:
    if not reasons:
        return []
    res = []
    for bit, name in THROTTLE_MAP:
        if (reasons & bit) and name not in res:
            res.append(name)
    return res


def _cpu_info() -> tuple[str | None, int | None]:
    try:
        import winreg

        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"HARDWARE\DESCRIPTION\System\CentralProcessor\0",
        )
        nome, _ = winreg.QueryValueEx(key, "ProcessorNameString")
        base, _ = winreg.QueryValueEx(key, "~MHz")
        winreg.CloseKey(key)
        nome_str = str(nome).strip() if nome is not None else None
        base_int = int(base) if base is not None else None
        return nome_str, base_int
    except Exception:
        return None, None


class _PDH_FMT_COUNTERVALUE_DOUBLE(ctypes.Structure):
    _fields_ = [
        ("CStatus", ctypes.c_ulong),
        ("doubleValue", ctypes.c_double),
    ]


class _PDH_ITEM(ctypes.Structure):
    _fields_ = [("szName", ctypes.c_wchar_p), ("FmtValue", _PDH_FMT_COUNTERVALUE_DOUBLE)]


def _pdh_array(pdh, counter) -> dict[str, float]:
    """Soma por nome de processo (svchost, chrome... agrupados) os valores de um contador curinga."""
    tam, n = ctypes.wintypes.DWORD(0), ctypes.wintypes.DWORD(0)
    fmt = 0x200 | 0x8000  # PDH_FMT_DOUBLE | PDH_FMT_NOCAP100
    pdh.PdhGetFormattedCounterArrayW(counter, fmt, ctypes.byref(tam), ctypes.byref(n), None)
    buf = ctypes.create_string_buffer(tam.value)
    st = pdh.PdhGetFormattedCounterArrayW(counter, fmt, ctypes.byref(tam), ctypes.byref(n), buf)
    if st != 0:
        raise RuntimeError(f"PdhGetFormattedCounterArrayW {st:#x}")
    itens = ctypes.cast(buf, ctypes.POINTER(_PDH_ITEM))
    soma: dict[str, float] = {}
    for i in range(n.value):
        it = itens[i]
        if it.FmtValue.CStatus in (0, 1) and it.szName:
            soma[it.szName] = soma.get(it.szName, 0.0) + it.FmtValue.doubleValue
    return soma


def _processos_pdh(ctx: dict) -> list[dict]:
    """Top 5 por CPU. CPU em % da maquina toda; RAM = working set privado (como o Gerenciador de Tarefas)."""
    if ctx.get("proc_pdh_desligado"):
        return []
    try:
        pdh = ctypes.windll.pdh
        if "proc_query" not in ctx:
            q, c_cpu, c_ram = ctypes.wintypes.HANDLE(), ctypes.wintypes.HANDLE(), ctypes.wintypes.HANDLE()
            if pdh.PdhOpenQueryW(None, 0, ctypes.byref(q)):
                raise RuntimeError("PdhOpenQueryW")
            for nome, h in (("\Process(*)\% Processor Time", c_cpu),
                            ("\Process(*)\Working Set - Private", c_ram)):
                if pdh.PdhAddEnglishCounterW(q, nome, 0, ctypes.byref(h)):
                    raise RuntimeError("PdhAddEnglishCounterW " + nome)
            pdh.PdhCollectQueryData(q)
            ctx["proc_query"], ctx["proc_counters"] = q, (c_cpu, c_ram)
            return []  # a primeira coleta so prepara a taxa de CPU
        if pdh.PdhCollectQueryData(ctx["proc_query"]):
            raise RuntimeError("PdhCollectQueryData")
        c_cpu, c_ram = ctx["proc_counters"]
        cpu, ram = _pdh_array(pdh, c_cpu), _pdh_array(pdh, c_ram)
        n = psutil.cpu_count() or 1
        lista = [{"nome": nome, "cpu_pct": round(v / n, 1), "ram_mb": int(ram.get(nome, 0) / 1048576)}
                 for nome, v in cpu.items() if nome not in ("_Total", "Idle")]
        lista.sort(key=lambda x: x["cpu_pct"], reverse=True)
        ctx["proc_falhas"] = 0
        return lista[:5]
    except Exception:
        ctx["proc_falhas"] = ctx.get("proc_falhas", 0) + 1
        if ctx["proc_falhas"] >= 3:
            ctx["proc_pdh_desligado"] = True
        return []


def _cpu_perf_pct(ctx: dict) -> float | None:
    if ctx.get("pdh_desligado"):
        return None

    try:
        windll = getattr(ctypes, "windll", None)
        if windll is None or not hasattr(windll, "pdh"):
            raise RuntimeError("pdh.dll não disponível")

        pdh = windll.pdh

        if "pdh_query" not in ctx or "pdh_counter" not in ctx:
            q = ctypes.wintypes.HANDLE()
            c = ctypes.wintypes.HANDLE()
            status = pdh.PdhOpenQueryW(None, 0, ctypes.byref(q))
            if status != 0:
                raise RuntimeError(f"PdhOpenQueryW status {status}")
            status = pdh.PdhAddEnglishCounterW(
                q,
                "\\Processor Information(_Total)\\% Processor Performance",
                0,
                ctypes.byref(c),
            )
            if status != 0:
                pdh.PdhCloseQuery(q)
                raise RuntimeError(f"PdhAddEnglishCounterW status {status}")
            status = pdh.PdhCollectQueryData(q)
            if status != 0:
                pdh.PdhCloseQuery(q)
                raise RuntimeError(f"PdhCollectQueryData status {status}")

            ctx["pdh_query"] = q
            ctx["pdh_counter"] = c
            ctx["pdh_falhas"] = 0
            return None

        q = ctx["pdh_query"]
        c = ctx["pdh_counter"]
        status = pdh.PdhCollectQueryData(q)
        if status != 0:
            raise RuntimeError(f"PdhCollectQueryData status {status}")

        fmt = _PDH_FMT_COUNTERVALUE_DOUBLE()
        status = pdh.PdhGetFormattedCounterValue(c, 0x200, None, ctypes.byref(fmt))
        if status != 0:
            raise RuntimeError(f"PdhGetFormattedCounterValue status {status}")

        ctx["pdh_falhas"] = 0
        return float(fmt.doubleValue)
    except Exception:
        falhas = ctx.get("pdh_falhas", 0) + 1
        ctx["pdh_falhas"] = falhas
        if falhas >= 3:
            ctx["pdh_desligado"] = True
            if "pdh_query" in ctx:
                try:
                    ctypes.windll.pdh.PdhCloseQuery(ctx["pdh_query"])
                except Exception:
                    pass
                ctx.pop("pdh_query", None)
                ctx.pop("pdh_counter", None)
        return None


def collect(cfg: dict, ctx: dict) -> dict:
    agora_mon = time.monotonic()

    # 1. CPU
    cpu_pct = round(psutil.cpu_percent(interval=None), 1)

    if "cpu_nome" not in ctx or "cpu_base_mhz" not in ctx:
        c_nome, c_base = _cpu_info()
        ctx["cpu_nome"] = c_nome
        ctx["cpu_base_mhz"] = c_base

    cpu_nome = ctx.get("cpu_nome")
    cpu_base_mhz = ctx.get("cpu_base_mhz")

    if "cpu_nucleos_fisicos" not in ctx:
        ctx["cpu_nucleos_fisicos"] = psutil.cpu_count(logical=False)
    cpu_nucleos_fisicos = ctx.get("cpu_nucleos_fisicos")

    per_cpu = psutil.cpu_percent(interval=None, percpu=True)
    cpu_nucleos = [round(float(x), 1) for x in per_cpu] if per_cpu else []

    perf_pct = _cpu_perf_pct(ctx)
    if perf_pct is not None and cpu_base_mhz is not None:
        cpu_clock_mhz = round(cpu_base_mhz * perf_pct / 100)
    else:
        cpu_clock_mhz = None

    # 2. RAM & Swap
    vm = psutil.virtual_memory()
    ram_pct = round(vm.percent, 1)
    ram_usado_gb = round(vm.used / (1024**3), 1)
    ram_total_gb = round(vm.total / (1024**3), 1)
    ram_disponivel_gb = round(vm.available / (1024**3), 1)

    try:
        sw = psutil.swap_memory()
        swap_pct = round(sw.percent, 1)
    except Exception:
        swap_pct = None

    # 3. Rede
    net = psutil.net_io_counters()
    if "net_bytes" in ctx and "net_time" in ctx and net is not None:
        dt = agora_mon - ctx["net_time"]
        if dt > 0:
            prev_recv, prev_sent = ctx["net_bytes"]
            down_bps = max(0.0, net.bytes_recv - prev_recv) / dt
            up_bps = max(0.0, net.bytes_sent - prev_sent) / dt
            rede_down_kbps = round(down_bps / 1024.0, 1)
            rede_up_kbps = round(up_bps / 1024.0, 1)
        else:
            rede_down_kbps = 0.0
            rede_up_kbps = 0.0
    else:
        rede_down_kbps = 0.0
        rede_up_kbps = 0.0

    if net is not None:
        ctx["net_bytes"] = (net.bytes_recv, net.bytes_sent)
        ctx["net_time"] = agora_mon

    # 4. Disco
    try:
        disk = psutil.disk_io_counters()
    except Exception:
        disk = None

    if "disk_bytes" in ctx and "disk_time" in ctx and disk is not None:
        dt_d = agora_mon - ctx["disk_time"]
        if dt_d > 0:
            prev_read, prev_write = ctx["disk_bytes"]
            read_bps = max(0.0, disk.read_bytes - prev_read) / dt_d
            write_bps = max(0.0, disk.write_bytes - prev_write) / dt_d
            disco_leitura_mbps = round(read_bps / (1024.0 * 1024.0), 1)
            disco_escrita_mbps = round(write_bps / (1024.0 * 1024.0), 1)
        else:
            disco_leitura_mbps = 0.0
            disco_escrita_mbps = 0.0
    else:
        disco_leitura_mbps = 0.0
        disco_escrita_mbps = 0.0

    if disk is not None:
        ctx["disk_bytes"] = (disk.read_bytes, disk.write_bytes)
        ctx["disk_time"] = agora_mon

    # 5. GPU via pynvml
    gpu_nome = None
    gpu_pct = None
    gpu_temp = None
    vram_usado_gb = None
    vram_total_gb = None
    gpu_clock_mhz = None
    gpu_clock_max_mhz = None
    gpu_mem_clock_mhz = None
    gpu_power_w = None
    gpu_power_limite_w = None
    gpu_fan_pct = None
    gpu_pstate = None
    gpu_mem_ctrl_pct = None
    gpu_enc_pct = None
    gpu_dec_pct = None
    gpu_pcie_rx_mbps = None
    gpu_pcie_tx_mbps = None
    gpu_temp_limite = None
    gpu_throttle = []
    gpu_driver = None

    if pynvml is not None and not ctx.get("nvml_falhou"):
        if "nvml_handle" not in ctx:
            try:
                pynvml.nvmlInit()
                ctx["nvml_handle"] = pynvml.nvmlDeviceGetHandleByIndex(0)
            except Exception:
                ctx["nvml_falhou"] = True

        handle = ctx.get("nvml_handle")
        if handle is not None:
            try:
                name = pynvml.nvmlDeviceGetName(handle)
                if isinstance(name, bytes):
                    name = name.decode("utf-8", errors="ignore")
                gpu_nome = str(name)
            except Exception:
                gpu_nome = None

            try:
                util = pynvml.nvmlDeviceGetUtilizationRates(handle)
                gpu_pct = int(util.gpu)
            except Exception:
                gpu_pct = None

            try:
                temp = pynvml.nvmlDeviceGetTemperature(handle, NVML_TEMPERATURE_GPU)
                gpu_temp = int(temp)
            except Exception:
                gpu_temp = None

            try:
                mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
                vram_usado_gb = round(mem.used / (1024**3), 1)
                vram_total_gb = round(mem.total / (1024**3), 1)
            except Exception:
                vram_usado_gb = None
                vram_total_gb = None

            try:
                gpu_clock_mhz = int(pynvml.nvmlDeviceGetClockInfo(handle, NVML_CLOCK_GRAPHICS))
            except Exception:
                gpu_clock_mhz = None

            try:
                gpu_clock_max_mhz = int(pynvml.nvmlDeviceGetMaxClockInfo(handle, NVML_CLOCK_GRAPHICS))
            except Exception:
                gpu_clock_max_mhz = None

            try:
                gpu_mem_clock_mhz = int(pynvml.nvmlDeviceGetClockInfo(handle, NVML_CLOCK_MEM))
            except Exception:
                gpu_mem_clock_mhz = None

            try:
                val = pynvml.nvmlDeviceGetPowerUsage(handle)
                gpu_power_w = round(val / 1000.0, 1)
            except Exception:
                gpu_power_w = None

            try:
                val = pynvml.nvmlDeviceGetEnforcedPowerLimit(handle)
                gpu_power_limite_w = round(val / 1000.0, 1)
            except Exception:
                gpu_power_limite_w = None

            try:
                gpu_fan_pct = int(pynvml.nvmlDeviceGetFanSpeed(handle))
            except Exception:
                gpu_fan_pct = None

            try:
                gpu_pstate = int(pynvml.nvmlDeviceGetPerformanceState(handle))
            except Exception:
                gpu_pstate = None

            try:
                gpu_mem_ctrl_pct = int(pynvml.nvmlDeviceGetUtilizationRates(handle).memory)
            except Exception:
                gpu_mem_ctrl_pct = None

            try:
                enc = pynvml.nvmlDeviceGetEncoderUtilization(handle)
                gpu_enc_pct = int(enc[0])
            except Exception:
                gpu_enc_pct = None

            try:
                dec = pynvml.nvmlDeviceGetDecoderUtilization(handle)
                gpu_dec_pct = int(dec[0])
            except Exception:
                gpu_dec_pct = None

            try:
                rx_kb = pynvml.nvmlDeviceGetPcieThroughput(handle, NVML_PCIE_UTIL_RX_BYTES)
                gpu_pcie_rx_mbps = round(float(rx_kb) / 1024.0, 1)
            except Exception:
                gpu_pcie_rx_mbps = None

            try:
                tx_kb = pynvml.nvmlDeviceGetPcieThroughput(handle, NVML_PCIE_UTIL_TX_BYTES)
                gpu_pcie_tx_mbps = round(float(tx_kb) / 1024.0, 1)
            except Exception:
                gpu_pcie_tx_mbps = None

            try:
                gpu_temp_limite = int(
                    pynvml.nvmlDeviceGetTemperatureThreshold(
                        handle, NVML_TEMPERATURE_THRESHOLD_SLOWDOWN
                    )
                )
            except Exception:
                gpu_temp_limite = None

            try:
                reasons = pynvml.nvmlDeviceGetCurrentClocksEventReasons(handle)
                gpu_throttle = _parse_throttle(reasons)
            except Exception:
                gpu_throttle = []

            try:
                drv = pynvml.nvmlSystemGetDriverVersion()
                if isinstance(drv, bytes):
                    drv = drv.decode("utf-8", errors="ignore")
                gpu_driver = str(drv)
            except Exception:
                gpu_driver = None

    # 6. cpu_temp (WMI)
    cpu_temp = None
    if not ctx.get("cpu_temp_desligado"):
        ultimo_teste = ctx.get("cpu_temp_time")
        if ultimo_teste is not None and (agora_mon - ultimo_teste) < 30.0:
            cpu_temp = ctx.get("cpu_temp_cache")
        else:
            ctx["cpu_temp_time"] = agora_mon
            try:
                cmd = [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    "(Get-CimInstance -Namespace root/wmi -ClassName MSAcpi_ThermalZoneTemperature -ErrorAction Stop).CurrentTemperature",
                ]
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
                if res.returncode != 0:
                    raise RuntimeError(f"powershell returncode {res.returncode}")

                valores = []
                for linha in res.stdout.strip().splitlines():
                    linha = linha.strip()
                    if not linha:
                        continue
                    for item in linha.split():
                        try:
                            valores.append(float(item))
                        except ValueError:
                            pass
                if not valores:
                    raise ValueError("Nenhum valor retornado")

                maior_k = max(valores)
                c = round(maior_k / 10.0 - 273.15, 1)
                ctx["cpu_temp_falhas"] = 0
                ctx["cpu_temp_cache"] = c
                cpu_temp = c
            except Exception:
                falhas = ctx.get("cpu_temp_falhas", 0) + 1
                ctx["cpu_temp_falhas"] = falhas
                if falhas >= 3:
                    ctx["cpu_temp_desligado"] = True
                ctx["cpu_temp_cache"] = None
                cpu_temp = None

    # 7. processos_top (PDH: uma consulta para todos os processos; psutil leva ~12 s aqui)
    if ctx.get("proc_time") is None or (agora_mon - ctx["proc_time"]) >= 3.0:
        ctx["proc_time"] = agora_mon
        ctx["processos_top"] = _processos_pdh(ctx)
    processos_top = ctx.get("processos_top") or []

    # 8. uptime_s
    try:
        uptime_s = int(time.time() - psutil.boot_time())
    except Exception:
        uptime_s = None

    return {
        "cpu_pct": cpu_pct,
        "cpu_temp": cpu_temp,
        "ram_pct": ram_pct,
        "ram_usado_gb": ram_usado_gb,
        "ram_total_gb": ram_total_gb,
        "gpu_nome": gpu_nome,
        "gpu_pct": gpu_pct,
        "gpu_temp": gpu_temp,
        "vram_usado_gb": vram_usado_gb,
        "vram_total_gb": vram_total_gb,
        "rede_down_kbps": rede_down_kbps,
        "rede_up_kbps": rede_up_kbps,
        "cpu_nome": cpu_nome,
        "cpu_nucleos_fisicos": cpu_nucleos_fisicos,
        "cpu_nucleos": cpu_nucleos,
        "cpu_clock_mhz": cpu_clock_mhz,
        "cpu_base_mhz": cpu_base_mhz,
        "ram_disponivel_gb": ram_disponivel_gb,
        "swap_pct": swap_pct,
        "gpu_clock_mhz": gpu_clock_mhz,
        "gpu_clock_max_mhz": gpu_clock_max_mhz,
        "gpu_mem_clock_mhz": gpu_mem_clock_mhz,
        "gpu_power_w": gpu_power_w,
        "gpu_power_limite_w": gpu_power_limite_w,
        "gpu_fan_pct": gpu_fan_pct,
        "gpu_pstate": gpu_pstate,
        "gpu_mem_ctrl_pct": gpu_mem_ctrl_pct,
        "gpu_enc_pct": gpu_enc_pct,
        "gpu_dec_pct": gpu_dec_pct,
        "gpu_pcie_rx_mbps": gpu_pcie_rx_mbps,
        "gpu_pcie_tx_mbps": gpu_pcie_tx_mbps,
        "gpu_temp_limite": gpu_temp_limite,
        "gpu_throttle": gpu_throttle,
        "gpu_driver": gpu_driver,
        "disco_leitura_mbps": disco_leitura_mbps,
        "disco_escrita_mbps": disco_escrita_mbps,
        "processos_top": processos_top,
        "uptime_s": uptime_s,
    }
