import os
import mmap
import struct
import sys
import time

PCI_ID = "0000:01:00.0"
BAR0_PATH = f"/sys/bus/pci/devices/{PCI_ID}/resource0"

# Target physical memory offsets
OFFSET_T1 = 0xAD0400
SENSORS =[0xAD04B8, 0xAD04BC, 0xAD04C0, 0xAD04C4]

def run_monitor():
    if not os.path.exists(BAR0_PATH):
        print(f"Cannot find BAR0 file: {BAR0_PATH}")
        sys.exit(1)

    try:
        # Open and map memory only once for maximum efficiency
        with open(BAR0_PATH, "rb") as f:
            mm = mmap.mmap(f.fileno(), length=0x1000000, access=mmap.ACCESS_READ)
            
            # Cache to store the last valid temperature for each sensor to prevent UI flickering
            last_valid_temps = {addr: 0.0 for addr in SENSORS}
            
            while True:
                # 1. Read Base Core Temp (T1) - extract the lowest byte
                mm.seek(OFFSET_T1)
                t1_raw = struct.unpack("<I", mm.read(4))[0]
                t1_temp = t1_raw & 0xFF  
                
                # 2. Read the 4 Array Sensors
                for addr in SENSORS:
                    mm.seek(addr)
                    val32 = struct.unpack("<I", mm.read(4))[0]
                    
                    upper_16 = val32 >> 16
                    # Accept the data as long as it's not a BADF placeholder and starts with 4000 or 0000
                    if upper_16 in (0x4000, 0x0000):
                        integer_part = (val32 >> 8) & 0xFF
                        fraction_part = val32 & 0xFF
                        real_temp = integer_part + (fraction_part / 256.0)
                        last_valid_temps[addr] = real_temp
                
                # ==========================================
                # Terminal UI Rendering
                # ==========================================
                # \033[2J\033[H clears the screen smoothly without flickering
                print("\033[2J\033[H", end="")
                current_time = time.strftime('%H:%M:%S')
                
                print(f"=== RTX 50 Series Low-Level Temperature Monitor[Time: {current_time}] ===")
                print(f"  Base Core Temp (T1, 0xAD0400) :  {t1_temp} °C")
                print("-" * 65)
                
                # Filter out initial 0.0 values (just in case they haven't been read yet)
                active_temps = {k: v for k, v in last_valid_temps.items() if v > 0}
                
                if active_temps:
                    core_avg = sum(active_temps.values()) / len(active_temps)
                    max_addr = max(active_temps, key=active_temps.get)
                    max_temp = active_temps[max_addr]
                    
                    # Print the 4 sensors (fixed positions, never disappear)
                    for addr in SENSORS:
                        t = last_valid_temps[addr]
                        if t == 0.0:
                            print(f"  Array Sensor 0x{addr:X}       :  [Waiting for data...]")
                        else:
                            marker = "  <-- [Hotspot / Tmax]" if addr == max_addr else ""
                            print(f"  Array Sensor 0x{addr:X}       :  {t:5.2f} °C{marker}")
                        
                    print("-" * 65)
                    print(f"  Array Avg Temp (Core Avg)   :  {core_avg:.2f} °C")
                    print(f"  Real-time Tmax              :  {max_temp:.2f} °C (from 0x{max_addr:X})")
                else:
                    print("  No valid hotspot array sensor data read yet...")
                
                print("\nPress Ctrl+C to exit monitoring...")
                time.sleep(1)

    except PermissionError:
        print("Error: This script must be run with sudo privileges!")
    except KeyboardInterrupt:
        print("\n\nExit signal received, monitoring stopped.")
    except Exception as e:
        print(f"Read error: {e}")
    finally:
        if 'mm' in locals() and not mm.closed:
            mm.close()

if __name__ == "__main__":
    run_monitor()