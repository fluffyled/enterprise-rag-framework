import subprocess,time,json,ctypes
from pathlib import Path
from ctypes import wintypes
R=Path(r'D:\хакатон\experiments\qwen35_public_2026-11-13')
class PMC(ctypes.Structure):
 _fields_=[('cb',wintypes.DWORD),('PageFaultCount',wintypes.DWORD)]+[(x,ctypes.c_size_t) for x in ['PeakWorkingSetSize','WorkingSetSize','QuotaPeakPagedPoolUsage','QuotaPagedPoolUsage','QuotaPeakNonPagedPoolUsage','QuotaNonPagedPoolUsage','PagefileUsage','PeakPagefileUsage']]
k=ctypes.WinDLL('kernel32');k.OpenProcess.restype=wintypes.HANDLE;k.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD]
p=ctypes.WinDLL('psapi');p.GetProcessMemoryInfo.argtypes=[wintypes.HANDLE,ctypes.POINTER(PMC),wintypes.DWORD]
h=k.OpenProcess(0x410,False,9332)
with (R/'resource_samples.jsonl').open('a',encoding='utf8') as f:
 while not (R/'STOP_MONITOR').exists():
  try:
   r=subprocess.run(['nvidia-smi','--query-gpu=memory.used,utilization.gpu','--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=5)
   c=PMC();c.cb=ctypes.sizeof(c);ok=p.GetProcessMemoryInfo(h,ctypes.byref(c),c.cb)
   f.write(json.dumps({'time':time.time(),'gpu_device_memory_mib':float(r.stdout.split(',')[0]),'gpu_utilization':float(r.stdout.split(',')[1]),'server_working_set_bytes':c.WorkingSetSize if ok else None,'server_peak_working_set_bytes':c.PeakWorkingSetSize if ok else None})+'\n');f.flush()
  except Exception:pass
  time.sleep(.5)
