# 3Shape TRIOS 3/4/5/6 Scanner Troubleshooting Knowledge Base

## Hardware & Connectivity Differences
- **TRIOS 3** relies on a USB-A 3.0 connection through the external power pod. Firmware below 1.4.9 is prone to USB selective suspend dropouts on Windows 10 21H1; disable USB power saving on hubs and upgrade to the latest Unite-certified firmware before swapping cables.
- **TRIOS 4** adds a smart battery and Wi-Fi for cordless operation. Frequent disconnects usually trace back to depleted batteries (below 15%) or outdated Wi-Fi dongle firmware. Cycle the batteries monthly and keep pod firmware at 1.6.x to stabilize wake-from-sleep behavior.
- **TRIOS 5** introduces a pen grip with LED status ring and a wireless charging puck. Most wake failures are caused by fouled contact pads—clean with 70% IPA and reseat the puck. Replace the magnetic cable if the LED stays amber after 30 minutes on charge.
- **TRIOS 6** ships with USB-C hardwiring and new field-replaceable tips with integrated thermal sensors. USB-C cables longer than 2 meters cause enumeration failures; stay with the 1.8-meter shielded cable bundled by 3Shape.

## Calibration & Optics
- Shared drift symptoms—washed-out surfaces, double contours, or occlusion holes—typically originate from loose or overheated tips. Confirm the tip glass is seated and under 40 °C, then run Unite → **Settings → Scanners → Calibrate**; expect green checks in 3–5 minutes.
- TRIOS 3/4 rely on the black/white calibration tile. If the tile warps or the matte finish wears out, scans skew 50–100 µm. Replace the tile annually.
- TRIOS 5/6 use the Sphere Calibration unit. Error 1060 usually means the sphere QR code is unreadable—clean the window and re-register the accessory under **Scanner Tools**.
- Calibration errors 3112/3113 often indicate that the Unite PC regional format uses a comma decimal separator. Set the format to use a dot or upgrade firmware to ≥1.5.2.

## Thermal & Fan Alerts
- TRIOS 3 internal fans clog easily in dusty labs. Unite logs will show warning 20102 (over-temperature). Blow compressed air through the vents and verify fan RPM via the TRIOS Diagnostic Tool; persistent warnings require a fan module swap.
- TRIOS 4 triggers “Battery Overheat” if scanning continuously on the Wi-Fi dock. Switch to pod power for long cases and update firmware to the 2022 Q4 thermal curve.
- TRIOS 5/6 log Code 47 when the tip thermistor exceeds 48 °C. Cool the tip under running water (do not submerge the handle) for 30 seconds and record ambient temps above 28 °C for escalation.

## Image Quality & Color Issues
- Grainy or color-shifted scans usually stem from smudged mirrors. Use lint-free swabs with 70% IPA—never acetone on TRIOS 5/6 sapphire windows.
- Firmware 1.7.x introduced HDR color capture. Ensure Unite 23.2 or later is installed; on PCs with Intel UHD 620 or older GPUs disable HDR in **Settings** to avoid stuttering.
- TRIOS 3 units that show banding often run mismatched pod firmware. Align pod and scanner firmware levels to eliminate exposure desync (Support FAQ ID 1157).

## Wireless & Battery Checks (TRIOS 4/5/6)
- Use the 3Shape Battery Tool to log cycle counts. Replace packs once capacity falls below 80% to avoid sudden shutdowns mid-scan.
- Wi-Fi dropouts on Move+ carts usually stem from DFS channel interference. Fix the access point to channel 36/40 and keep the scanner within 5 meters line-of-sight.
- LED sequence reference: solid green = ready, pulsing blue = pairing, flashing red = thermal fault, pulsing amber = low battery.

## Software & Licensing
- Unite must be 22.1 or newer for TRIOS 5/6 recognition. If scanners are missing, remove residual USB drivers (**Device Manager → View hidden devices → Universal Serial Bus devices**) and reinstall Unite.
- License expiration warnings after RMA shipments appear when the faulty device is not returned within 32 days. Confirm the RMA case in 3Shape eSupport shows “device received” before closure.
- When moving scanners between clinics, de-register them under Unite → **Accounts** so calibration data unlocks for the new site.

## Escalation Triggers
- Collect logs from `C:\ProgramData\3Shape\Logs\TRIOS` and include the `.tdslog` files.
- Document firmware, pod serial, tip serial, battery cycles, and Unite version.
- Capture photos of error messages and the condition of tips, calibration targets, and charging docks.
- Escalate immediately if the scanner emits a burning odor, throws recurring Error 4110 (laser fault), or fails the LED self-test at startup.
