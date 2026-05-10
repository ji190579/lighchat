import psutil
vm = psutil.virtual_memory()
print(f'Total: {vm.total//1024//1024} MB')
print(f'Used: {vm.used//1024//1024} MB')
print(f'Available: {vm.available//1024//1024} MB')
total = 0
for p in psutil.process_iter():
    try:
        cmd = ' '.join(p.cmdline())
        if 'uvicorn' in cmd or ('python' in cmd.lower() and 'lighchat' in cmd):
            mem = p.memory_info().rss//1024//1024
            total += mem
            print(f'PID {p.pid}: {mem} MB -> {cmd[:50]}')
    except:
        pass
print(f'Total backend: {total} MB')
