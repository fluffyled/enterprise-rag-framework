"""Run after dot-sourcing project-env.ps1: GPU math and CUDA JIT compilation."""
import ctypes
import os
from pathlib import Path

# Configure project storage before importing model libraries.
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import answering
import torch

assert torch.cuda.is_available(), 'CUDA GPU is unavailable'
x = torch.arange(1024, dtype=torch.float32, device='cuda')
assert (x * x).sum().item() == 357389824.0
matrix = torch.eye(256, device='cuda')
assert torch.equal(matrix @ matrix, matrix)
torch.cuda.synchronize()
print('PyTorch:', torch.__version__, 'CUDA:', torch.version.cuda)
print('GPU:', torch.cuda.get_device_name(0), '- GPU computations passed')

cuda = Path(os.environ['CUDA_PATH'])
dll_dir = os.add_dll_directory(str(cuda / 'bin'))
nvrtc = ctypes.WinDLL(str(next(p for p in (cuda / 'bin').glob('nvrtc64_*.dll') if '.alt.' not in p.name)))
program = ctypes.c_void_p()
source = b'extern "C" __global__ void square(float* x) { int i=threadIdx.x; x[i]*=x[i]; }'
assert nvrtc.nvrtcCreateProgram(ctypes.byref(program), source, b'check.cu', 0, None, None) == 0
try:
    options = (ctypes.c_char_p * 1)(b'--gpu-architecture=compute_86')
    status = nvrtc.nvrtcCompileProgram(program, 1, options)
    if status:
        size = ctypes.c_size_t()
        nvrtc.nvrtcGetProgramLogSize(program, ctypes.byref(size))
        log = ctypes.create_string_buffer(size.value)
        nvrtc.nvrtcGetProgramLog(program, log)
        raise RuntimeError(log.value.decode())
    size = ctypes.c_size_t()
    assert nvrtc.nvrtcGetPTXSize(program, ctypes.byref(size)) == 0
    assert size.value > 0
    print('CUDA kernel compilation passed:', size.value, 'bytes of PTX')
finally:
    nvrtc.nvrtcDestroyProgram(ctypes.byref(program))
