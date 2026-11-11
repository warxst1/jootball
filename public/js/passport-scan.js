(() => {
    'use strict';

    const root = document.getElementById('passportScan');
    if (!root) return;
    const status = root.querySelector('[role="status"]');
    const pickers = root.querySelectorAll('input[type=file]');
    const scanUrl = root.dataset.scanUrl;
    let busy = false;

    function apply({ sex, ...values }) {
        const sexInput = sex ? document.getElementById(sex === 'M' ? 'sex_m' : 'sex_w') : null;
        const existingSex = document.querySelector('input[name=sex]:checked');
        const changesSex = sexInput && existingSex && existingSex !== sexInput;
        const fields = Object.fromEntries(Object.keys(values).map(key => [key, document.getElementById(key)]));
        if (changesSex || Object.keys(values).some(key => values[key] && fields[key].value.trim() && fields[key].value !== values[key])) {
            if (!window.confirm('แทนที่ข้อมูลเดิมในช่องที่อ่านได้จากพาสปอร์ตหรือไม่?')) return false;
        }

        const existingId = fields.id_card.value;
        fields.id_card.dataset.passport = 'true';
        if (fields.nation.value !== values.nation) {
            fields.nation.value = values.nation;
            fields.nation.dispatchEvent(new Event('change', { bubbles: true }));
        }
        if (window.jQuery) {
            const id = window.jQuery(fields.id_card);
            if (typeof id.unmask === 'function') id.unmask();
        }
        fields.id_card.value = existingId;
        for (const [key, value] of Object.entries(values)) {
            if (value) fields[key].value = value;
        }
        if (sexInput) sexInput.checked = true;
        return true;
    }

    const cameraButton = root.querySelector('[data-open-camera]');
    const cameraFile = root.querySelector('[data-camera-file]');
    const panel = root.querySelector('[data-camera-panel]');
    const preview = panel.querySelector('video');
    const shutter = panel.querySelector('[data-take-photo]');
    let cameraRequest = 0;
    const selection = root.querySelector('[data-passport-selection]');
    const selectedImage = selection.querySelector('img');
    const scanButton = selection.querySelector('[data-scan-selected]');
    const resetButton = selection.querySelector('[data-reset-selected]');
    const reviewPanel = root.querySelector('[data-passport-review]');
    const reviewFields = root.querySelector('[data-review-fields]');
    const reviewMrz = root.querySelector('[data-review-mrz]');
    const reviewChecks = root.querySelector('[data-review-checks]');
    const applyButton = root.querySelector('[data-apply-passport]');
    const cropButton = root.querySelector('[data-crop-passport]');
    root.querySelector('[data-close-review]').addEventListener('click', () => reviewPanel.close());
    reviewPanel.addEventListener('click', event => {
        if (event.target !== reviewPanel) return;
        const bounds = reviewPanel.getBoundingClientRect();
        if (event.clientX < bounds.left || event.clientX > bounds.right
            || event.clientY < bounds.top || event.clientY > bounds.bottom) reviewPanel.close();
    });
    let pendingValues = null;
    let selectedFile = null;

    function clearReview() {
        pendingValues = null;
        if (reviewPanel.open) reviewPanel.close();
        cropButton.hidden = true;
        reviewFields.replaceChildren();
        reviewMrz.textContent = '';
        reviewChecks.replaceChildren();
    }

    function showReview(result) {
        if (!result.mrz) return;
        if (!reviewPanel.open) reviewPanel.showModal();
        reviewMrz.textContent = result.mrz.join('\n');
        for (const check of result.checks) {
            const item = document.createElement('li');
            item.className = 'list-group-item px-0';
            item.textContent = check.label + ' · อ่านได้ ' + check.observed + ' / คำนวณ ' +
                check.expected + ' · ' + (check.pass ? 'PASS' : 'FAIL');
            item.classList.add(check.pass ? 'text-success' : 'text-danger');
            reviewChecks.append(item);
        }
        pendingValues = result.values || null;
        applyButton.hidden = !pendingValues;
        if (!pendingValues) return;
        cropButton.hidden = false;
        const { nationality, issuer, expiry } = result.details;
        for (const [label, value] of [
            ['เลขพาสปอร์ต', pendingValues.id_card],
            ['ชื่อจริง', pendingValues.first_name],
            ['นามสกุล', pendingValues.last_name],
            ['รหัสสัญชาติ', nationality],
            ['รหัสประเทศผู้ออก', issuer],
            ['เพศ', pendingValues.sex === 'W' ? 'หญิง' : pendingValues.sex === 'M' ? 'ชาย' : ''],
            ['วันเกิด (ปีที่อนุมาน)', pendingValues.birth_date],
            ['วันหมดอายุ', expiry],
        ]) {
            const term = document.createElement('dt');
            const description = document.createElement('dd');
            term.className = 'col-sm-6';
            description.className = 'col-sm-6';
            term.textContent = label;
            description.textContent = value || '—';
            reviewFields.append(term, description);
        }
    }

    cropButton.addEventListener('click', () => {
        if (!pendingValues || !selectedFile) return;
        reviewPanel.close();
        document.getElementById('cropperModal').dispatchEvent(
            new CustomEvent('passport-portrait', { detail: selectedFile }),
        );
    });

    applyButton.addEventListener('click', () => {
        if (!pendingValues || !apply(pendingValues)) return;
        reviewPanel.close();
        const input = document.getElementById('idCardFileInput');
        const transfer = new DataTransfer();
        transfer.items.add(selectedFile);
        input.files = transfer.files;
        input.dispatchEvent(new Event('change', { bubbles: true }));
        status.textContent = 'เติมข้อมูลแล้ว กรุณาตรวจรูปเอกสารและข้อมูลก่อนบันทึก';
    });
    let previewUrl = '';

    function selectImage(file) {
        if (busy) return;
        closeCamera();
        if (previewUrl) URL.revokeObjectURL(previewUrl);
        clearReview();
        selectedFile = file;
        previewUrl = file ? URL.createObjectURL(file) : '';
        selection.hidden = !file;
        if (file) {
            selectedImage.src = previewUrl;
            selection.querySelector('[data-passport-filename]').textContent = file.name || 'ภาพจากกล้อง';
        } else {
            selectedImage.removeAttribute('src');
        }
        status.textContent = file ? 'ตรวจภาพให้เห็น MRZ ทั้งสองบรรทัด แล้วกดสแกนพาสปอร์ต' : '';
    }

    scanButton.addEventListener('click', () => scan(selectedFile));
    resetButton.addEventListener('click', () => selectImage(null));


    function closeCamera() {
        cameraRequest++;
        if (preview.srcObject) {
            for (const track of preview.srcObject.getTracks()) track.stop();
            preview.srcObject = null;
        }
        shutter.disabled = true;
        panel.hidden = true;
    }

    cameraButton.addEventListener('click', async () => {
        if (busy || !panel.hidden) return;
        if (!navigator.mediaDevices?.getUserMedia) {
            status.textContent = 'เปิดกล้องในหน้าเว็บไม่ได้ ลองถ่ายหรือเลือกรูปจากอุปกรณ์';
            cameraFile.click();
            return;
        }

        const request = ++cameraRequest;
        panel.hidden = false;
        status.textContent = 'กำลังเปิดกล้อง…';
        try {
            const stream = await navigator.mediaDevices.getUserMedia({
                audio: false,
                video: { facingMode: { ideal: 'environment' }, width: { ideal: 1920 } },
            });
            if (request !== cameraRequest) {
                for (const track of stream.getTracks()) track.stop();
                return;
            }
            preview.srcObject = stream;
            await preview.play();
            if (request !== cameraRequest) return;
            shutter.disabled = false;
            status.textContent = '';
        } catch {
            if (request !== cameraRequest) return;
            closeCamera();
            status.textContent = 'เปิดกล้องไม่ได้ ตรวจสิทธิ์กล้องของเบราว์เซอร์ หรือกดเลือกรูป';
        }
    });

    shutter.addEventListener('click', () => {
        if (!preview.videoWidth || !preview.videoHeight) return;
        const canvas = document.createElement('canvas');
        canvas.width = preview.videoWidth;
        canvas.height = preview.videoHeight;
        canvas.getContext('2d').drawImage(preview, 0, 0);
        closeCamera();
        canvas.toBlob(file => {
            if (file) selectImage(file);
        }, 'image/jpeg', 0.95);
    });
    panel.querySelector('[data-close-camera]').addEventListener('click', closeCamera);
    root.addEventListener('hide.bs.collapse', closeCamera);
    window.addEventListener('pagehide', closeCamera);

    for (const picker of pickers) {
        picker.addEventListener('change', () => {
            const file = picker.files[0];
            picker.value = '';
            if (file) selectImage(file);
        });
    }

    async function scan(file) {
        if (!file || busy) return;
        closeCamera();
        clearReview();
        busy = true;
        cameraButton.disabled = scanButton.disabled = resetButton.disabled = true;
        for (const input of pickers) input.disabled = true;
        status.textContent = 'กำลังอ่านพาสปอร์ต…';
        try {
            const type = file.type || (/\.png$/i.test(file.name) ? 'image/png' : 'image/jpeg');
            const response = await fetch(scanUrl, {
                method: 'POST',
                headers: { 'Content-Type': type, 'X-Requested-With': 'XMLHttpRequest' },
                body: file,
                cache: 'no-store',
                redirect: 'error',
            });
            const payload = await response.json();
            if (!Array.isArray(payload.mrz)) {
                status.textContent = payload.errors?.[0]?.message || 'อ่าน MRZ ไม่ได้ กรุณาลองใหม่';
                return;
            }
            const data = payload.data;
            const birth = payload.dates?.date_of_birth;
            const values = {
                first_name: data.first_name,
                last_name: data.last_name,
                id_card: data.passport_number,
                birth_date: data.date_of_birth?.split('-').reverse().join('/') || '',
                nation: data.nationality === 'THA' ? 'THAI' : data.nationality ? 'OTHER' : '',
                sex: data.sex === 'F' ? 'W' : data.sex === 'M' ? 'M' : '',
            };
            const labels = {
                passport_number: 'เลขพาสปอร์ต', date_of_birth: 'วันเกิด',
                date_of_expiry: 'วันหมดอายุ', optional_data: 'ข้อมูลเสริม', composite: 'Composite',
            };
            const verified = response.ok && payload.status === 'review_required';
            showReview({
                mrz: payload.mrz,
                checks: Object.entries(payload.checks).map(([key, check]) => ({
                    label: labels[key], observed: check.observed, expected: check.expected,
                    pass: check.status === 'PASS',
                })),
                details: {
                    nationality: data.nationality,
                    issuer: data.issuing_country,
                    expiry: data.date_of_expiry || payload.dates?.date_of_expiry?.raw,
                },
                values: verified ? values : null,
            });
            const normalized = payload.ocr_mrz ? ' · ระบบปรับ 0 เป็น O ในรหัสประเทศ กรุณาตรวจทาน' : '';
            if (!verified) {
                status.textContent = 'Check Digit ไม่ผ่าน · ตรวจภาพหรือถ่ายใหม่';
            } else if (!values.birth_date) {
                const candidates = birth?.candidates?.join(' / ');
                status.textContent = 'ตรวจข้อมูลก่อนนำลงฟอร์ม · กรุณากรอกวันเกิดจากต้นฉบับ' +
                    (candidates ? ' (' + candidates + ')' : '') + normalized;
            } else {
                status.textContent = 'Check Digit ผ่าน · ตรวจข้อมูลแล้วกดนำข้อมูลลงฟอร์ม' + normalized;
            }
        } catch {
            status.textContent = 'ติดต่อระบบสแกนไม่ได้ กรุณาตรวจว่าเข้าสู่ระบบและเปิด Backend OCR แล้ว';
        } finally {
            busy = false;
            cameraButton.disabled = scanButton.disabled = resetButton.disabled = false;
            for (const input of pickers) input.disabled = false;
        }
    }

    root.querySelector('[data-manual]').addEventListener('click', () => {
        closeCamera();
        document.getElementById('first_name').focus();
    });
})();
