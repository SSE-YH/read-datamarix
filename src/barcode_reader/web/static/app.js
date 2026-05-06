(() => {
  "use strict";

  const BYTES_PER_MIB = 1024 * 1024;
  const MAX_FILE_BYTES = 20 * BYTES_PER_MIB;
  const MAX_TOTAL_BYTES = 250 * BYTES_PER_MIB;
  const MAX_FILES = 100;
  const ACCEPTED_EXTENSIONS = new Set([
    "jpg",
    "jpeg",
    "jfif",
    "png",
    "bmp",
    "tif",
    "tiff",
  ]);
  const MIME_BY_EXTENSION = {
    jpg: "image/jpeg",
    jpeg: "image/jpeg",
    jfif: "image/jpeg",
    png: "image/png",
    bmp: "image/bmp",
    tif: "image/tiff",
    tiff: "image/tiff",
  };
  const ACCEPTED_MIME_TYPES = new Set(Object.values(MIME_BY_EXTENSION));
  const FINAL_JOB_STATUSES = new Set(["completed", "partial_failed", "failed"]);
  const POLL_INTERVAL_MS = 1400;
  const MAX_POLL_ERRORS = 5;

  const STATUS_LABELS = {
    idle: "대기",
    uploading: "업로드 중",
    queued: "대기 중",
    processing: "분석 중",
    completed: "완료",
    partial_failed: "부분 실패",
    failed: "실패",
  };

  const IMAGE_STATUS_LABELS = {
    success: "성공",
    not_found: "미검출",
    decode_failed: "해독 실패",
    error: "오류",
  };

  const ERROR_CODE_LABELS = {
    no_files: "이미지를 하나 이상 선택하세요.",
    too_many_files: `한 번에 ${MAX_FILES}개까지만 업로드할 수 있습니다.`,
    total_size_exceeded: `전체 용량은 ${formatBytes(MAX_TOTAL_BYTES)} 이하여야 합니다.`,
    unsupported_extension: "지원하지 않는 파일 확장자입니다.",
    unsupported_mime_type: "지원하지 않는 이미지 형식입니다.",
    empty_file: "빈 파일은 업로드할 수 없습니다.",
    file_too_large: `파일 하나는 ${formatBytes(MAX_FILE_BYTES)} 이하여야 합니다.`,
    invalid_image: "이미지 파일을 열 수 없습니다.",
    image_dimensions_exceeded: "이미지 가로 또는 세로가 허용 범위를 넘었습니다.",
    image_pixels_exceeded: "이미지 픽셀 수가 허용 범위를 넘었습니다.",
  };

  const els = {
    dropzone: document.getElementById("dropzone"),
    fileInput: document.getElementById("fileInput"),
    browseButton: document.getElementById("browseButton"),
    clearButton: document.getElementById("clearButton"),
    uploadButton: document.getElementById("uploadButton"),
    clientError: document.getElementById("clientError"),
    selectionStats: document.getElementById("selectionStats"),
    fileList: document.getElementById("fileList"),
    statusTitle: document.getElementById("status-title"),
    statusBadge: document.getElementById("statusBadge"),
    progressBar: document.getElementById("progressBar"),
    progressText: document.getElementById("progressText"),
    metricTotal: document.getElementById("metricTotal"),
    metricProcessed: document.getElementById("metricProcessed"),
    metricSuccess: document.getElementById("metricSuccess"),
    metricFailure: document.getElementById("metricFailure"),
    serverMessage: document.getElementById("serverMessage"),
    downloadCsv: document.getElementById("downloadCsv"),
    retryStatusButton: document.getElementById("retryStatusButton"),
    resultPanel: document.getElementById("resultPanel"),
    resultList: document.getElementById("resultList"),
    jobIdText: document.getElementById("jobIdText"),
  };

  let selectedItems = [];
  let idCounter = 0;
  let currentXhr = null;
  let activeJob = null;
  let pollTimer = null;
  let pollErrors = 0;

  els.browseButton.addEventListener("click", () => els.fileInput.click());
  els.fileInput.addEventListener("change", (event) => {
    addFiles(event.target.files);
    els.fileInput.value = "";
  });
  els.clearButton.addEventListener("click", clearSelections);
  els.uploadButton.addEventListener("click", uploadSelectedFiles);
  els.retryStatusButton.addEventListener("click", () => {
    if (activeJob?.links?.status) {
      pollErrors = 0;
      pollJobNow();
    }
  });

  els.dropzone.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      els.fileInput.click();
    }
  });

  ["dragenter", "dragover"].forEach((eventName) => {
    els.dropzone.addEventListener(eventName, (event) => {
      event.preventDefault();
      els.dropzone.classList.add("is-dragging");
    });
  });

  ["dragleave", "drop"].forEach((eventName) => {
    els.dropzone.addEventListener(eventName, (event) => {
      event.preventDefault();
      els.dropzone.classList.remove("is-dragging");
    });
  });

  els.dropzone.addEventListener("drop", (event) => {
    addFiles(event.dataTransfer.files);
  });

  window.addEventListener("beforeunload", () => {
    clearPolling();
    revokeAllPreviews();
  });

  renderSelection();
  renderJob(null);

  function addFiles(fileList) {
    const files = Array.from(fileList || []);
    if (!files.length) {
      return;
    }

    for (const file of files) {
      selectedItems.push({
        id: `file_${Date.now()}_${idCounter++}`,
        file,
        previewUrl: file.type.startsWith("image/") ? URL.createObjectURL(file) : "",
      });
    }

    hideMessage(els.clientError);
    renderSelection();
  }

  function clearSelections() {
    if (currentXhr) {
      currentXhr.abort();
      currentXhr = null;
    }
    revokeAllPreviews();
    selectedItems = [];
    activeJob = null;
    clearPolling();
    hideMessage(els.clientError);
    hideMessage(els.serverMessage);
    setStage("idle", "이미지를 선택하면 업로드할 수 있습니다.", 0);
    renderSelection();
    renderJob(null);
  }

  function removeSelection(id) {
    const item = selectedItems.find((candidate) => candidate.id === id);
    if (item?.previewUrl) {
      URL.revokeObjectURL(item.previewUrl);
    }
    selectedItems = selectedItems.filter((candidate) => candidate.id !== id);
    renderSelection();
  }

  function revokeAllPreviews() {
    for (const item of selectedItems) {
      if (item.previewUrl) {
        URL.revokeObjectURL(item.previewUrl);
      }
    }
  }

  function renderSelection() {
    const totalBytes = selectedItems.reduce((sum, item) => sum + item.file.size, 0);
    const fileIssues = selectedItems.flatMap((item) => fileValidationMessages(item.file));
    const selectionIssues = selectionValidationMessages(totalBytes);
    const issueCount = fileIssues.length + selectionIssues.length;

    els.selectionStats.textContent = `${selectedItems.length} files, ${formatBytes(totalBytes)}`;
    els.clearButton.disabled = selectedItems.length === 0 && !activeJob;
    els.uploadButton.disabled = !canUpload(issueCount);

    renderClientIssues(selectionIssues);
    els.fileList.replaceChildren(...selectedItems.map(renderFileItem));
  }

  function renderFileItem(item) {
    const file = item.file;
    const messages = fileValidationMessages(file);
    const extension = fileExtension(file.name).toUpperCase() || "FILE";
    const li = document.createElement("li");
    li.className = `file-card ${messages.length ? "invalid" : "valid"}`;

    const thumb = document.createElement("div");
    thumb.className = "thumb";
    if (item.previewUrl) {
      const image = document.createElement("img");
      image.src = item.previewUrl;
      image.alt = "";
      thumb.append(image);
    } else {
      thumb.textContent = extension.slice(0, 5);
    }

    const body = document.createElement("div");
    const name = document.createElement("div");
    name.className = "file-name";
    name.textContent = file.name || "upload";
    const meta = document.createElement("div");
    meta.className = "file-meta";
    meta.textContent = `${formatBytes(file.size)} | ${file.type || MIME_BY_EXTENSION[fileExtension(file.name)] || extension}`;
    const badges = document.createElement("div");
    badges.className = "badge-row";
    if (messages.length) {
      for (const message of messages) {
        const badge = document.createElement("span");
        badge.className = "pill bad";
        badge.textContent = message;
        badges.append(badge);
      }
    } else {
      const badge = document.createElement("span");
      badge.className = "pill ok";
      badge.textContent = "준비됨";
      badges.append(badge);
    }
    body.append(name, meta, badges);

    const remove = document.createElement("button");
    remove.className = "remove-button";
    remove.type = "button";
    remove.textContent = "x";
    remove.setAttribute("aria-label", `${file.name || "file"} 제거`);
    remove.addEventListener("click", () => removeSelection(item.id));

    li.append(thumb, body, remove);
    return li;
  }

  function renderClientIssues(selectionIssues) {
    if (!selectionIssues.length) {
      hideMessage(els.clientError);
      return;
    }
    showMessage(els.clientError, "선택한 파일을 확인하세요.", selectionIssues, "error");
  }

  function canUpload(issueCount) {
    return selectedItems.length > 0 && issueCount === 0 && !currentXhr;
  }

  function fileValidationMessages(file) {
    const messages = [];
    const extension = fileExtension(file.name);
    if (!ACCEPTED_EXTENSIONS.has(extension)) {
      messages.push("지원하지 않는 확장자");
    }
    if (file.size === 0) {
      messages.push("빈 파일");
    } else if (file.size > MAX_FILE_BYTES) {
      messages.push("20 MiB 초과");
    }
    return messages;
  }

  function selectionValidationMessages(totalBytes) {
    const messages = [];
    if (selectedItems.length > MAX_FILES) {
      messages.push(`한 번에 ${MAX_FILES}개까지만 업로드할 수 있습니다.`);
    }
    if (totalBytes > MAX_TOTAL_BYTES) {
      messages.push(`전체 용량은 ${formatBytes(MAX_TOTAL_BYTES)} 이하여야 합니다.`);
    }
    return messages;
  }

  function uploadSelectedFiles() {
    const totalBytes = selectedItems.reduce((sum, item) => sum + item.file.size, 0);
    const issueCount =
      selectedItems.flatMap((item) => fileValidationMessages(item.file)).length +
      selectionValidationMessages(totalBytes).length;
    if (!canUpload(issueCount)) {
      renderSelection();
      return;
    }

    clearPolling();
    activeJob = null;
    pollErrors = 0;
    hideMessage(els.clientError);
    hideMessage(els.serverMessage);
    renderJob(null);
    setStage("uploading", "업로드 중입니다.", 4);
    renderSelection();

    const formData = new FormData();
    for (const item of selectedItems) {
      formData.append("images", fileForUpload(item.file), item.file.name);
    }

    const xhr = new XMLHttpRequest();
    currentXhr = xhr;
    xhr.open("POST", "/api/uploads");
    xhr.responseType = "json";

    xhr.upload.addEventListener("progress", (event) => {
      if (!event.lengthComputable) {
        setStage("uploading", "업로드 중입니다.", 18);
        return;
      }
      const percent = Math.max(4, Math.round((event.loaded / event.total) * 45));
      setStage("uploading", `업로드 중입니다. ${percent}%`, percent);
    });

    xhr.addEventListener("load", () => {
      currentXhr = null;
      const body = parseXhrBody(xhr);
      if (xhr.status >= 200 && xhr.status < 300) {
        setStage("processing", "서버가 이미지를 분석하고 있습니다.", 55);
        setActiveJob(body);
      } else {
        const error = formatApiError(body, xhr.status);
        showMessage(els.serverMessage, error.title, error.messages, "error");
        setStage("failed", "업로드가 완료되지 않았습니다.", 0);
      }
      renderSelection();
    });

    xhr.addEventListener("error", () => {
      currentXhr = null;
      showMessage(
        els.serverMessage,
        "네트워크 오류가 발생했습니다.",
        ["서버 연결을 확인한 뒤 다시 시도하세요."],
        "error",
      );
      setStage("failed", "업로드가 완료되지 않았습니다.", 0);
      renderSelection();
    });

    xhr.addEventListener("abort", () => {
      setStage("idle", "업로드가 취소되었습니다.", 0);
      renderSelection();
    });

    xhr.send(formData);
  }

  function parseXhrBody(xhr) {
    if (xhr.response && typeof xhr.response === "object") {
      return xhr.response;
    }
    try {
      return JSON.parse(xhr.responseText);
    } catch {
      return null;
    }
  }

  function setActiveJob(job) {
    if (!job || typeof job !== "object") {
      showMessage(
        els.serverMessage,
        "서버 응답을 읽을 수 없습니다.",
        ["잠시 뒤 다시 업로드하세요."],
        "error",
      );
      setStage("failed", "업로드가 완료되지 않았습니다.", 0);
      return;
    }

    activeJob = job;
    hideMessage(els.serverMessage);
    renderJob(job);
    updateStageFromJob(job);

    if (job.links?.status && !FINAL_JOB_STATUSES.has(job.status)) {
      schedulePoll();
    } else {
      clearPolling();
    }
  }

  function schedulePoll(delayMs = POLL_INTERVAL_MS) {
    clearPolling();
    pollTimer = window.setTimeout(pollJobNow, delayMs);
  }

  async function pollJobNow() {
    clearPolling();
    if (!activeJob?.links?.status) {
      return;
    }

    try {
      const response = await fetch(activeJob.links.status, { cache: "no-store" });
      const body = await response.json();
      if (!response.ok) {
        throw new Error(body?.detail?.message || `HTTP ${response.status}`);
      }
      pollErrors = 0;
      els.retryStatusButton.hidden = true;
      setActiveJob(body);
    } catch (error) {
      pollErrors += 1;
      const retrying = pollErrors <= MAX_POLL_ERRORS;
      showMessage(
        els.serverMessage,
        retrying ? "상태를 다시 확인하는 중입니다." : "상태 확인이 멈췄습니다.",
        [retrying ? "네트워크가 복구되면 자동으로 이어집니다." : String(error.message || error)],
        retrying ? "warning" : "error",
      );
      els.retryStatusButton.hidden = retrying;
      if (retrying) {
        schedulePoll(POLL_INTERVAL_MS * pollErrors);
      }
    }
  }

  function clearPolling() {
    if (pollTimer) {
      window.clearTimeout(pollTimer);
      pollTimer = null;
    }
  }

  function renderJob(job) {
    const hasJob = Boolean(job);
    els.resultPanel.hidden = !hasJob;
    els.metricTotal.textContent = String(job?.totalImages || 0);
    els.metricProcessed.textContent = String(job?.processedImages || 0);
    els.metricSuccess.textContent = String(job?.successCount || 0);
    els.metricFailure.textContent = String(job?.failureCount || 0);

    if (!hasJob) {
      els.jobIdText.textContent = "";
      els.resultList.replaceChildren();
      configureDownload(null);
      return;
    }

    els.jobIdText.textContent = job.jobId || "";
    els.resultList.replaceChildren(...(job.images || []).map(renderResultItem));
    configureDownload(job);

    if (job.errorMessage) {
      showMessage(els.serverMessage, "작업 오류", [job.errorMessage], "error");
    }
  }

  function renderResultItem(image) {
    const li = document.createElement("li");
    li.className = "result-item";

    const body = document.createElement("div");
    const name = document.createElement("div");
    name.className = "result-name";
    name.textContent = image.sourceFilename || "upload";

    const meta = document.createElement("div");
    meta.className = "result-meta";
    const detail = [
      `#${image.imageIndex || "-"}`,
      formatBytes(image.sizeBytes || 0),
      `${image.resultCount || 0} results`,
    ];
    if (image.errorMessage) {
      detail.push(image.errorMessage);
    }
    meta.textContent = detail.join(" | ");
    body.append(name, meta);

    const state = document.createElement("span");
    const status = image.status || "processing";
    state.className = `pill result-state ${status === "success" ? "ok" : "bad"}`;
    state.textContent = IMAGE_STATUS_LABELS[status] || status;

    li.append(body, state);
    return li;
  }

  function configureDownload(job) {
    if (job?.csvReady && job.links?.csv) {
      els.downloadCsv.href = job.links.csv;
      els.downloadCsv.classList.remove("disabled");
      els.downloadCsv.setAttribute("aria-disabled", "false");
      els.downloadCsv.setAttribute("download", `${job.jobId || "barcode-results"}.csv`);
    } else {
      els.downloadCsv.href = "#";
      els.downloadCsv.classList.add("disabled");
      els.downloadCsv.setAttribute("aria-disabled", "true");
      els.downloadCsv.removeAttribute("download");
    }
  }

  function updateStageFromJob(job) {
    const total = Number(job.totalImages || 0);
    const processed = Number(job.processedImages || 0);
    const percent = total ? Math.round((processed / total) * 100) : 0;
    const status = job.status || "processing";
    let text = `${processed}/${total}개 처리됨`;
    if (job.csvReady) {
      text += " | CSV 준비 완료";
    }
    setStage(status, text, FINAL_JOB_STATUSES.has(status) ? 100 : percent);
  }

  function setStage(status, text, percent) {
    const normalized = STATUS_LABELS[status] ? status : "idle";
    els.statusTitle.textContent = STATUS_LABELS[normalized];
    els.statusBadge.textContent = STATUS_LABELS[normalized];
    els.statusBadge.className = `status-badge ${normalized}`;
    els.progressText.textContent = text;
    els.progressBar.style.width = `${Math.max(0, Math.min(100, percent))}%`;
  }

  function showMessage(element, title, messages, tone = "info") {
    element.hidden = false;
    element.className = `message ${tone === "error" ? "is-error" : ""} ${
      tone === "warning" ? "is-warning" : ""
    }`.trim();
    element.replaceChildren();
    const titleElement = document.createElement("strong");
    titleElement.textContent = title;
    element.append(titleElement);
    if (messages?.length) {
      const list = document.createElement("ul");
      for (const message of messages) {
        const item = document.createElement("li");
        item.textContent = message;
        list.append(item);
      }
      element.append(list);
    }
  }

  function hideMessage(element) {
    element.hidden = true;
    element.replaceChildren();
  }

  function formatApiError(body, status) {
    const detail = body?.detail;
    if (detail?.errors && Array.isArray(detail.errors)) {
      return {
        title: "업로드가 거부되었습니다.",
        messages: detail.errors.map((error) => {
          const file = error.filename ? `${error.filename}: ` : "";
          return `${file}${ERROR_CODE_LABELS[error.code] || error.message || "파일을 확인하세요."}`;
        }),
      };
    }
    if (detail?.message) {
      return { title: "요청을 처리할 수 없습니다.", messages: [detail.message] };
    }
    if (typeof detail === "string") {
      return { title: "요청을 처리할 수 없습니다.", messages: [detail] };
    }
    return {
      title: "요청을 처리할 수 없습니다.",
      messages: [`서버 응답 코드: ${status || "unknown"}`],
    };
  }

  function fileExtension(filename) {
    const name = filename || "";
    const index = name.lastIndexOf(".");
    return index >= 0 ? name.slice(index + 1).toLowerCase() : "";
  }

  function fileForUpload(file) {
    const mappedType = MIME_BY_EXTENSION[fileExtension(file.name)];
    if (!mappedType || ACCEPTED_MIME_TYPES.has(file.type)) {
      return file;
    }
    if (typeof File === "function") {
      return new File([file], file.name || "upload", {
        type: mappedType,
        lastModified: file.lastModified,
      });
    }
    return file.slice(0, file.size, mappedType);
  }

  function formatBytes(bytes) {
    const value = Number(bytes || 0);
    if (value < 1024) {
      return `${value} B`;
    }
    if (value < BYTES_PER_MIB) {
      return `${(value / 1024).toFixed(1)} KiB`;
    }
    return `${(value / BYTES_PER_MIB).toFixed(1)} MiB`;
  }
})();
