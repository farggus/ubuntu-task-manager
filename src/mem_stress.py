import time
import sys

chunk_size = 100 * 1024 * 1024 # 100 MB
chunks = []
target_gb = 12

print(f"Eating memory up to {target_gb} GB...")

try:
    for i in range(target_gb * 10):
        chunks.append(bytearray(chunk_size))
        # Touch memory to make it real
        chunks[-1][0] = 1
        time.sleep(0.1)
        if i % 10 == 0:
            print(f"Allocated {(i+1)*100} MB")
            sys.stdout.flush()
    
    print("Done. Holding...")
    time.sleep(300)
except MemoryError:
    print("OOM reached!")
    time.sleep(300)
except KeyboardInterrupt:
    pass
