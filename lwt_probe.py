import time, paho.mqtt.client as mqtt
t0 = None
def on_connect(c, u, flags, rc, props):
    print("[PROBE] connected", flush=True)
    c.subscribe("prime-factory/status", qos=1)
def on_message(c, u, msg):
    global t0
    now = time.time()
    d = "" if t0 is None else f"   (+{now - t0:.2f}s)"
    t0 = now
    print(f"{time.strftime('%H:%M:%S')}  {msg.payload.decode():8s} retain={msg.retain}{d}", flush=True)
cl = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2, client_id="lwt_probe")
cl.on_connect = on_connect
cl.on_message = on_message
cl.connect("localhost", 1883, 60)
cl.loop_forever()