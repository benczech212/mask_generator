import threading

def run_in_thread():
    import signal
    import gmsh
    
    original_signal = signal.signal
    def dummy_signal(signum, handler): return signal.SIG_DFL
    
    try:
        signal.signal = dummy_signal
        if not gmsh.isInitialized():
            gmsh.initialize()
            print("Successfully initialized in thread!")
    except Exception as e:
        print(f"Failed in thread: {type(e).__name__}: {e}")
    finally:
        signal.signal = original_signal
        if gmsh.isInitialized():
            gmsh.finalize()

t = threading.Thread(target=run_in_thread)
t.start()
t.join()
