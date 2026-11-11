# Backend OCR สำหรับ Jootball

ติดตั้ง Python 3.12 และ Tesseract บนเครื่องที่รัน PHP พร้อมเปิด PHP cURL
ดาวน์โหลด ocrb.traineddata จาก https://github.com/Shreeshrii/tessdata_ocrb และตรวจใบอนุญาตต้นทางก่อนใช้งาน เก็บโมเดลในโฟลเดอร์ backend
โมเดลและโปรแกรม Tesseract ต้องติดตั้งเพิ่มเติมเมื่อย้ายเครื่อง

เปิด PowerShell จาก backend แล้วรันคำสั่งตามลำดับ

    py -3.12 -m venv .venv
    .\.venv\Scripts\python.exe -m pip install -r requirements.txt
    $env:TESSERACT_CMD = 'C:\Program Files\Tesseract-OCR\tesseract.exe'
    $env:TESSDATA_PREFIX = (Get-Location).Path
    .\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log

PHP proxy อยู่ที่ modules/Player/Controllers/PassportScan.php และเชื่อมไป 127.0.0.1:8000 จึงต้องรัน Backend ในเครื่องหรือ network namespace เดียวกับ PHP
บนเว็บจริงใช้ HTTPS และจัดการ Backend เป็น service ตามสภาพแวดล้อมบริษัท

ทดสอบ parser จาก backend

    .\.venv\Scripts\python.exe -m unittest discover -s tests

ทดสอบใน staging ด้วยภาพจำลองทั้งสแกนผ่าน อ่านไม่ครบ Check Digit ผิด การเปิดกล้อง ปิดป๊อปอัป นำข้อมูลลงฟอร์ม และบันทึกนักเตะก่อน deploy
หลีกเลี่ยงการเก็บภาพ MRZ และเลขพาสปอร์ตเต็มใน log รวมถึงระบบ monitoring
