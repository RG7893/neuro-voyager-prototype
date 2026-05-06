# neuro-voyager-prototype
A basic Brain-Controlled Neurogaming Project on Windows. If your ATTENTION metric is High, the game will keep proceeding and eventually reach next level, if your MEDITATION metric is High, you will lose the game.

EEG Headset Used: FT&S Mindlink EEG Headband (Single-Channel, Bluetooth-enabled)

NeuroSky App used for establishing connection: https://store.neurosky.com/products/mindwave-mobile-tutorial-pc-mac

Check "Ports (COM & LPT)" section before and after pairng the EEG Headset using Blootooth.

Some new COM ports will be found. In my case, before pairing, "COM3" and "COM4" were present. Two new COM ports "COM5" and "COM6" were added after pairing.

After pairing, the Bluetooth settings will show "Paired, Not Connected" for the EEG Headset.

Install and open the MindWave Mobile Tutorial app, if it asks for the COM port, select "AUTO" and try connecting. It may not connect once, try connecting 2-3 times, it will display which COM port is connected, they are the one of the new COM ports ("COM5" or "COM6" in this case). At this stage, the Bluetooth settings will show "Paired, Connected" for the EEG Headset.

Enter the exact COM port ("COM5" or "COM6" in this case) in "neuro_voyager_v3_final.py" line 17 and run the program. The game window will appear and playing can be started.

If it doesn't connect, try re-entering each new COM port (trying both COM5 and COM6 in this case) one-by-one in "neuro_voyager_v3_final.py" line 17 and run the program again each time.
