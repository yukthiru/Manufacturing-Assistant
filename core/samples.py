"""Fictional sample manuals (used by tests and `seed_demo --samples`)."""

PRESS_MAINTENANCE = [
    "Hydraulic Press HP-200 Maintenance Manual, Revision B.\nDaily inspection: Check the hydraulic oil level in the reservoir sight glass before the first shift. Inspect hoses and fittings for leaks. Verify that the emergency stop button functions.",
    "Lubrication and filters: Replace the hydraulic oil filter every 500 operating hours. Use ISO VG 46 hydraulic oil only. Drain and replace the reservoir oil every 2000 operating hours. Normal operating pressure is 180 bar; never exceed 210 bar.",
]
PRESS_SAFETY = [
    "Hydraulic Press HP-200 Safety Supplement, Revision A.\nLockout procedure: Before servicing, switch off and lock the main electrical isolator, release stored hydraulic pressure using the relief valve, and attach a personal lockout tag.",
]
LATHE_MAINTENANCE = [
    "CNC Lathe CL-50 Maintenance Manual, Revision C.\nSpindle care: Grease the spindle bearings every 200 operating hours using lithium complex grease NLGI 2. Do not over-grease; two pumps per bearing is sufficient.",
    "Coolant system: Check coolant concentration weekly and keep it between 6 and 8 percent. Clean the chip tray at the end of every shift. Replace the coolant completely every 3 months.",
]

SAMPLES = {
    "HP-200_Maintenance_RevB.pdf": PRESS_MAINTENANCE,
    "HP-200_Safety_RevA.pdf": PRESS_SAFETY,
    "CL-50_Maintenance_RevC.pdf": LATHE_MAINTENANCE,
}


def make_pdf(pages) -> bytes:
    import fitz

    doc = fitz.open()
    for text in pages:
        page = doc.new_page()
        page.insert_textbox(fitz.Rect(50, 50, 550, 780), text, fontsize=11)
    data = doc.tobytes()
    doc.close()
    return data
