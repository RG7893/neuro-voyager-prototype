# neuro-voyager-prototype
Brain Controlled Neurogaming Project on Windows.

EEG Headset Used: FT&S Mindlink EEG Headband (Single-Channel, Bluetooth-enabled)

NeuroSky App used for establishing connection: https://store.neurosky.com/products/mindwave-mobile-tutorial-pc-mac

Check "Ports (COM & LPT)" section before and after pairng the EEG Headset using Blootooth. After pairing, the Bluetooth settings will show "Paired, Not Connected" for the EEG Headset.

Some new COM ports will be found. In my case, before pairing, "COM3" and "COM4" were present. Two new ports "COM5" and "COM6" were added after pairing.

Install and open the MindWave Mobile Tutorial app, if it asks for the COM port, select "AUTO" and try connecting. It may not connect once, try connecting 2-3 times, it will display which COM port is connected, they are the one of the new COM ports. "COM5" or "COM6" in this case.

