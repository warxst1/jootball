<?php

namespace Modules\Player\Controllers;

use App\Controllers\BaseController;

class PassportScan extends BaseController
{
    public function scan()
    {
        $response = $this->response->setHeader('Cache-Control', 'no-store');
        $fail = static function ($status, $code, $message) use ($response) {
            return $response->setStatusCode($status)->setJSON([
                'status' => 'error',
                'errors' => [['code' => $code, 'message' => $message]],
            ]);
        };

        if ($this->request->getHeaderLine('X-Requested-With') !== 'XMLHttpRequest') {
            return $fail(403, 'INVALID_REQUEST', 'คำขอไม่ถูกต้อง');
        }
        $type = strtolower(trim(explode(';', $this->request->getHeaderLine('Content-Type'), 2)[0]));
        if (!in_array($type, ['image/jpeg', 'image/png'], true)) {
            return $fail(415, 'UNSUPPORTED_IMAGE', 'รองรับเฉพาะไฟล์ JPEG และ PNG');
        }
        $maxBytes = 10 * 1024 * 1024;
        if ((int) $this->request->getHeaderLine('Content-Length') > $maxBytes) {
            return $fail(413, 'IMAGE_TOO_LARGE', 'ขนาดไฟล์ต้องไม่เกิน 10 MiB');
        }
        $body = file_get_contents('php://input', false, null, 0, $maxBytes + 1);
        if ($body === false || $body === '') {
            return $fail(422, 'INVALID_IMAGE', 'กรุณาเลือกภาพพาสปอร์ต');
        }
        if (strlen($body) > $maxBytes) {
            return $fail(413, 'IMAGE_TOO_LARGE', 'ขนาดไฟล์ต้องไม่เกิน 10 MiB');
        }
        if (!function_exists('curl_init')) {
            return $fail(503, 'OCR_UNAVAILABLE', 'กรุณาเปิด PHP cURL ใน XAMPP');
        }

        $handle = curl_init('http://127.0.0.1:8000/api/passport/scan');
        curl_setopt_array($handle, [
            CURLOPT_POST => true,
            CURLOPT_POSTFIELDS => $body,
            CURLOPT_HTTPHEADER => ['Content-Type: ' . $type],
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_CONNECTTIMEOUT => 3,
            CURLOPT_TIMEOUT => 30,
            CURLOPT_PROXY => '',
        ]);
        $result = curl_exec($handle);
        $status = curl_getinfo($handle, CURLINFO_HTTP_CODE);
        curl_close($handle);
        $payload = $result !== false ? json_decode($result, true) : null;
        if ($status < 200 || $status > 599 || !is_array($payload) || !isset($payload['status'])) {
            return $fail(503, 'OCR_UNAVAILABLE', 'เชื่อมต่อ Backend OCR ไม่ได้ กรุณาเปิด Scanner API ที่พอร์ต 8000');
        }
        return $response->setStatusCode($status)->setJSON($payload);
    }
}