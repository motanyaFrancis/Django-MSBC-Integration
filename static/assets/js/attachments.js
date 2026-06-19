/* ============================================================
   GLOBAL ATTACHMENT UPLOAD — attachments.js
   Self-contained drag-and-drop upload module.

   Usage
   -----
   1.  Include this file and attachments.css globally (base template).
   2.  Drop the modal HTML snippet anywhere on the page.
   3.  Open the modal from any button:
         data-bs-toggle="modal" data-bs-target="#attachmentModal"
         data-upload-url="/leave-attachments/{{ res.No_ }}/"
         data-doc-no="{{ res.No_ }}"
         data-table-name="Leave"          ← optional label shown in modal
   4.  Listen for the custom event if you need to react after upload:
         document.addEventListener('dz:uploaded', function(e) {
             console.log(e.detail.docNo, e.detail.count);
         });
   ============================================================ */

(function () {
    'use strict';

    /* ── Accepted extensions ──────────────────────────────── */
    var ACCEPTED_EXT = [
        'pdf', 'doc', 'docx', 'xls', 'xlsx',
        'jpg', 'jpeg', 'png', 'txt', 'ppt', 'pptx'
    ];
    var ACCEPTED_ATTR = ACCEPTED_EXT.map(function (e) { return '.' + e; }).join(',');
    var MAX_MB = 10;
    var MAX_BYTES = MAX_MB * 1024 * 1024;

    /* ── State ────────────────────────────────────────────── */
    var selectedFiles = [];   // Array<File>
    var uploadUrl = '';
    var docNo = '';

    /* ── CSRF helper ──────────────────────────────────────── */
    function csrf() {
        var m = document.cookie.match(/csrftoken=([^;]+)/);
        return m ? m[1] : '';
    }

    /* ── Format bytes ─────────────────────────────────────── */
    function fmtSize(bytes) {
        if (bytes < 1024) return bytes + ' B';
        if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
        return (bytes / 1048576).toFixed(1) + ' MB';
    }

    /* ── Derive icon class from filename ──────────────────── */
    function iconClass(name) {
        var ext = (name.split('.').pop() || '').toLowerCase();
        if (ext === 'pdf') return 'dz-pdf';
        if (['doc', 'docx'].indexOf(ext) > -1) return 'dz-doc';
        if (['xls', 'xlsx'].indexOf(ext) > -1) return 'dz-sheet';
        if (['jpg', 'jpeg', 'png', 'gif', 'webp'].indexOf(ext) > -1) return 'dz-img';
        if (['ppt', 'pptx'].indexOf(ext) > -1) return 'dz-ppt';
        if (ext === 'txt') return 'dz-txt';
        return 'dz-other';
    }

    /* ── Icon glyph (mdi) ─────────────────────────────────── */
    function iconGlyph(name) {
        var ext = (name.split('.').pop() || '').toLowerCase();
        if (ext === 'pdf') return 'mdi mdi-file-pdf-box';
        if (['doc', 'docx'].indexOf(ext) > -1) return 'mdi mdi-file-word';
        if (['xls', 'xlsx'].indexOf(ext) > -1) return 'mdi mdi-file-excel';
        if (['jpg', 'jpeg', 'png', 'gif', 'webp'].indexOf(ext) > -1) return 'mdi mdi-file-image';
        if (['ppt', 'pptx'].indexOf(ext) > -1) return 'mdi mdi-file-powerpoint';
        if (ext === 'txt') return 'mdi mdi-file-document-outline';
        return 'mdi mdi-file-outline';
    }

    /* ── Validate a File object ───────────────────────────── */
    function validate(file) {
        var ext = (file.name.split('.').pop() || '').toLowerCase();
        if (ACCEPTED_EXT.indexOf(ext) === -1) {
            return 'File type .' + ext + ' is not allowed.';
        }
        if (file.size > MAX_BYTES) {
            return file.name + ' exceeds the ' + MAX_MB + ' MB limit.';
        }
        return null;
    }

    /* ── Render the file list ─────────────────────────────── */
    function renderFileList() {
        var list = document.getElementById('dzFileList');
        var hint = document.getElementById('dzEmptyHint');
        var zone = document.getElementById('dzZone');
        if (!list) return;
        list.innerHTML = '';

        if (selectedFiles.length === 0) {
            if (hint) hint.style.display = 'block';
            if (zone) zone.classList.remove('dz-has-files');
            return;
        }
        if (hint) hint.style.display = 'none';
        if (zone) zone.classList.add('dz-has-files');

        selectedFiles.forEach(function (file, idx) {
            var li = document.createElement('li');
            li.className = 'dz-file-item';
            li.innerHTML =
                '<div class="dz-file-icon ' + iconClass(file.name) + '">' +
                '<i class="' + iconGlyph(file.name) + '"></i>' +
                '</div>' +
                '<div class="dz-file-meta">' +
                '<div class="dz-file-name" title="' + file.name + '">' + file.name + '</div>' +
                '<div class="dz-file-size">' + fmtSize(file.size) + '</div>' +
                '</div>' +
                '<button type="button" class="dz-file-remove" data-idx="' + idx + '" title="Remove">' +
                '<i class="mdi mdi-close"></i>' +
                '</button>';
            list.appendChild(li);
        });
    }

    /* ── Add files (dedup by name+size) ──────────────────── */
    function addFiles(fileList) {
        var errors = [];
        Array.prototype.forEach.call(fileList, function (file) {
            var err = validate(file);
            if (err) { errors.push(err); return; }
            var dup = selectedFiles.some(function (f) {
                return f.name === file.name && f.size === file.size;
            });
            if (!dup) selectedFiles.push(file);
        });
        if (errors.length) showResult(errors.join(' '), false);
        renderFileList();
        updateUploadBtn();
    }

    /* ── Remove one file ──────────────────────────────────── */
    function removeFile(idx) {
        selectedFiles.splice(idx, 1);
        renderFileList();
        updateUploadBtn();
    }

    /* ── Toggle upload button state ───────────────────────── */
    function updateUploadBtn() {
        var btn = document.getElementById('dzUploadBtn');
        if (btn) btn.disabled = selectedFiles.length === 0;
    }

    /* ── Show inline result message ───────────────────────── */
    function showResult(msg, ok) {
        var el = document.getElementById('dzResult');
        if (!el) return;
        el.textContent = msg;
        el.className = 'dz-result ' + (ok ? 'dz-ok' : 'dz-fail');
        el.style.display = 'block';
    }

    function clearResult() {
        var el = document.getElementById('dzResult');
        if (el) { el.style.display = 'none'; el.textContent = ''; }
    }

    /* ── Reset entire zone ────────────────────────────────── */
    function resetZone() {
        selectedFiles = [];
        renderFileList();
        updateUploadBtn();
        clearResult();
        var progress = document.getElementById('dzProgress');
        if (progress) progress.style.display = 'none';
        var bar = document.getElementById('dzProgressBar');
        if (bar) { bar.style.width = '0%'; bar.textContent = ''; }
        var pct = document.getElementById('dzProgressPct');
        if (pct) pct.textContent = '0%';
        var fi = document.getElementById('dzFileInput');
        if (fi) fi.value = '';
    }

    /* ── Perform the upload ───────────────────────────────── */
    function doUpload() {
        if (!selectedFiles.length || !uploadUrl) return;
        clearResult();

        var formData = new FormData();
        selectedFiles.forEach(function (f) {
            formData.append('attachments', f);
        });
        formData.append('csrfmiddlewaretoken', csrf());

        var btn = document.getElementById('dzUploadBtn');
        var progress = document.getElementById('dzProgress');
        var bar = document.getElementById('dzProgressBar');
        var pct = document.getElementById('dzProgressPct');
        var label = document.getElementById('dzProgressLabel');

        if (btn) {
            btn.disabled = true;
            btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Uploading…';
        }
        if (progress) progress.style.display = 'block';

        var xhr = new XMLHttpRequest();

        /* Upload progress */
        xhr.upload.addEventListener('progress', function (e) {
            if (!e.lengthComputable) return;
            var p = Math.round((e.loaded / e.total) * 100);
            if (bar) bar.style.width = p + '%';
            if (pct) pct.textContent = p + '%';
            if (label) label.textContent = fmtSize(e.loaded) + ' / ' + fmtSize(e.total);
        });

        xhr.addEventListener('load', function () {
            if (btn) {
                btn.disabled = false;
                btn.innerHTML = '<i class="mdi mdi-upload me-1"></i> Upload Files';
            }

            var data;
            try { data = JSON.parse(xhr.responseText); } catch (e) { data = {}; }

            if (xhr.status >= 200 && xhr.status < 300 && data.success !== false) {
                var count = selectedFiles.length;
                showResult(
                    (data.message || (count + ' file' + (count > 1 ? 's' : '') + ' uploaded successfully.')),
                    true
                );
                resetZone();

                /* Global toast if iziToast is loaded */
                if (window.iziToast) {
                    iziToast.success({
                        title: 'Uploaded',
                        message: data.message || count + ' file(s) uploaded successfully.',
                        position: 'topCenter',
                        timeout: 4000,
                        theme: 'dark',
                        backgroundColor: '#198754',
                        titleColor: '#fff',
                        messageColor: '#fff',
                        progressBarColor: '#fff',
                        maxWidth: '420px',
                        transitionIn: 'fadeInDown',
                        transitionOut: 'fadeOutUp'
                    });
                }

                /* Dispatch custom event so parent page can refresh attachment list */
                document.dispatchEvent(new CustomEvent('dz:uploaded', {
                    detail: { docNo: docNo, count: count }
                }));

                /* Auto-close modal after short delay */
                setTimeout(function () {
                    var modal = document.getElementById('attachmentModal');
                    if (modal && window.bootstrap) {
                        bootstrap.Modal.getInstance(modal).hide();
                    }
                }, 1400);

                reloadAfter(1500);

            } else {
                var errMsg = (data && data.error) ? data.error : 'Upload failed. Please try again.';
                showResult(errMsg, false);
                if (progress) progress.style.display = 'none';
                if (window.iziToast) {
                    iziToast.error({
                        title: 'Upload Failed',
                        message: errMsg,
                        position: 'topCenter',
                        timeout: 5000,
                        theme: 'dark',
                        backgroundColor: '#dc3545',
                        titleColor: '#fff',
                        messageColor: '#fff',
                        progressBarColor: '#fff',
                        maxWidth: '420px',
                        transitionIn: 'fadeInDown',
                        transitionOut: 'fadeOutUp'
                    });
                }
            }
        });

        xhr.addEventListener('error', function () {
            if (btn) {
                btn.disabled = false;
                btn.innerHTML = '<i class="mdi mdi-upload me-1"></i> Upload Files';
            }
            showResult('Network error. Please check your connection and try again.', false);
            if (progress) progress.style.display = 'none';
        });

        xhr.open('POST', uploadUrl, true);
        xhr.send(formData);
    }

    /* ── Boot once DOM is ready ───────────────────────────── */
    function boot() {
        var modal = document.getElementById('attachmentModal');
        var zone = document.getElementById('dzZone');
        var input = document.getElementById('dzFileInput');
        var list = document.getElementById('dzFileList');
        var upBtn = document.getElementById('dzUploadBtn');
        var docTitle = document.getElementById('dzDocTitle');

        if (!modal || !zone || !input) return; /* modal not in this page */

        /* Populate state from trigger button's data attributes */
        modal.addEventListener('show.bs.modal', function (e) {
            var trigger = e.relatedTarget;
            if (trigger) {
                uploadUrl = trigger.getAttribute('data-upload-url') || '';
                docNo = trigger.getAttribute('data-doc-no') || '';
                var label = trigger.getAttribute('data-table-name') || 'Document';
                if (docTitle) docTitle.textContent = label + ': ' + docNo;
            }
            resetZone();
        });

        /* Reset state on close */
        modal.addEventListener('hidden.bs.modal', function () {
            resetZone();
        });

        /* ── Drop zone drag events ── */
        zone.addEventListener('dragenter', function (e) {
            e.preventDefault(); zone.classList.add('dz-over');
        });
        zone.addEventListener('dragover', function (e) {
            e.preventDefault(); zone.classList.add('dz-over');
        });
        zone.addEventListener('dragleave', function (e) {
            if (!zone.contains(e.relatedTarget)) zone.classList.remove('dz-over');
        });
        zone.addEventListener('drop', function (e) {
            e.preventDefault();
            zone.classList.remove('dz-over');
            if (e.dataTransfer && e.dataTransfer.files.length) {
                addFiles(e.dataTransfer.files);
            }
        });

        /* Click zone → trigger hidden input */
        zone.addEventListener('click', function (e) {
            if (e.target.closest('.dz-browse-btn') || e.target.classList.contains('dz-browse-btn')) {
                e.stopPropagation();
            }
            input.click();
        });

        /* Browse button also triggers input */
        var browseBtn = zone.querySelector('.dz-browse-btn');
        if (browseBtn) {
            browseBtn.addEventListener('click', function (e) {
                e.stopPropagation();
                input.click();
            });
        }

        /* Hidden file input change */
        input.addEventListener('change', function () {
            if (this.files.length) addFiles(this.files);
            this.value = ''; /* allow re-selecting same file */
        });

        /* Remove file from list */
        if (list) {
            list.addEventListener('click', function (e) {
                var removeBtn = e.target.closest('.dz-file-remove');
                if (removeBtn) {
                    var idx = parseInt(removeBtn.getAttribute('data-idx'), 10);
                    removeFile(idx);
                }
            });
        }

        /* Upload button */
        if (upBtn) {
            upBtn.addEventListener('click', doUpload);
        }

        /* Keyboard: Space/Enter on zone opens picker */
        zone.setAttribute('tabindex', '0');
        zone.addEventListener('keydown', function (e) {
            if (e.key === ' ' || e.key === 'Enter') {
                e.preventDefault();
                input.click();
            }
        });

        /* Initial state */
        updateUploadBtn();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', boot);
    } else {
        boot();
    }

})();

/* ── Reload after delay ───────────────────────────────────────── */
function reloadAfter(ms) {
    setTimeout(function () { location.reload(); }, ms || 1000);
}