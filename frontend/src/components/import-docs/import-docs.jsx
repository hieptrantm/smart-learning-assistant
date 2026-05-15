import { useState, useRef, useEffect, useCallback } from "react";
import "./import-docs.css";
import {
  Upload,
  X,
  CheckCircle2,
  BookOpen,
  Trash2,
  Plus,
  Clock,
  Calendar,
  Target,
  FileText,
  GraduationCap,
  Star,
  ChevronDown,
  AlertCircle,
  Edit3,
  CalendarDays,
  Timer,
  Loader2,
  RefreshCw,
  Loader2Icon,
} from "lucide-react";
import { useIngestorService } from "../../service/ingestor/useIngestorService";
import { usePlannerService } from "../../service/planner/usePlannerService";
import { getGoogleToken } from "../../service/auth/googleToken";
import { useRequestCalendarToken } from "../../service/auth/googleAuth";
import toast from "react-hot-toast";

const DAYS_OF_WEEK = [
  { key: "mon", label: "Thứ 2" },
  { key: "tue", label: "Thứ 3" },
  { key: "wed", label: "Thứ 4" },
  { key: "thu", label: "Thứ 5" },
  { key: "fri", label: "Thứ 6" },
  { key: "sat", label: "Thứ 7" },
  { key: "sun", label: "CN" },
];

const TIME_SLOTS = [
  "06:00", "07:00", "08:00", "09:00", "10:00", "11:00",
  "12:00", "13:00", "14:00", "15:00", "16:00", "17:00",
  "18:00", "19:00", "20:00", "21:00", "22:00",
];

const EMOJIS = ["📚", "📐", "💻", "🌍", "🧪", "🎨", "📊", "🔬", "📝", "🎵", "⚡", "🧮", "🏛️", "🩺", "📡"];

const ImportDocs = ({ user }) => {
  const [subjects, setSubjects] = useState([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  const [showModal, setShowModal] = useState(false);
  const [files, setFiles] = useState([]);
  const [dragActive, setDragActive] = useState(false);
  const [selectedEmoji, setSelectedEmoji] = useState("📚");
  const [subjectName, setSubjectName] = useState("");
  const [targetGrade, setTargetGrade] = useState(7);
  const [endDate, setEndDate] = useState("");
  const [freeTime, setFreeTime] = useState({});
  const [isDraggingTime, setIsDraggingTime] = useState(false);
  const [dragMode, setDragMode] = useState(null);
  const [showEmojiPicker, setShowEmojiPicker] = useState(false);
  const [editingSubject, setEditingSubject] = useState(null);

  const fileInputRef = useRef(null);
  const modalRef = useRef(null);

  const { getSubjects, createSubject, updateSubject, deleteSubject: deleteSubjectApi, ingest} = useIngestorService();
  const requestCalendarToken = useRequestCalendarToken();
  const [googleToken, setGoogleTokenState] = useState(() => getGoogleToken());

  // ── Load subjects from ingestor API ────────────────────────
  const refreshSubjects = useCallback(async () => {
    try {
      const data = await getSubjects();
      setSubjects(data);
    } catch (err) {
      console.error("Failed to refresh subjects:", err);
    }
  }, [getSubjects]);

  const loadSubjects = useCallback(async () => {
    try {
      setLoading(true);
      await refreshSubjects();
    } catch (err) {
      console.error("Failed to load subjects:", err);
    } finally {
      setLoading(false);
    }
  }, [refreshSubjects]);

  useEffect(() => {
    if (user) loadSubjects();
  }, [user, loadSubjects]);

  // Auto-polling: refresh every 5s while any subject is still processing
  useEffect(() => {
    if (!user) return;

    const hasProcessing = subjects.some(
      (s) => s.ingest_status === "processing" || s.plan_status === "generating"
    );
    if (!hasProcessing) return;

    const timer = setInterval(refreshSubjects, 5000);
    return () => clearInterval(timer);
  }, [subjects, user, refreshSubjects]);

  // Get occupied time slots from other subjects
  const getOccupiedSlots = (excludeSubjectId = null) => {
    const occupied = {};
    subjects.forEach((s) => {
      if (s.id === excludeSubjectId) return;
      const ft = s.free_time || s.freeTime || {};
      Object.entries(ft).forEach(([day, slots]) => {
        if (!occupied[day]) occupied[day] = new Set();
        slots.forEach((slot) => occupied[day].add(slot));
      });
    });
    return occupied;
  };

  const occupiedSlots = getOccupiedSlots(editingSubject);

  const isSlotOccupied = (day, time) => {
    return occupiedSlots[day]?.has(time) || false;
  };

  // Close modal on Escape
  const resetForm = useCallback(() => {
    setFiles([]);
    setSubjectName("");
    setTargetGrade(7);
    setEndDate("");
    setFreeTime({});
    setSelectedEmoji("📚");
    setShowEmojiPicker(false);
    setEditingSubject(null);
  }, []);

  const closeModal = useCallback(() => {
    setShowModal(false);
    resetForm();
  }, [resetForm]);

  useEffect(() => {
    const handleKey = (e) => {
      if (e.key === "Escape" && showModal) closeModal();
    };
    document.addEventListener("keydown", handleKey);
    if (showModal) document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", handleKey);
      document.body.style.overflow = "";
    };
  }, [showModal, closeModal]);

  const openEditModal = (subject) => {
    setEditingSubject(subject.id);
    setSubjectName(subject.name);
    setSelectedEmoji(subject.emoji);
    setTargetGrade(subject.target_grade || subject.targetGrade);
    setEndDate(subject.end_date || subject.endDate || "");
    setFreeTime(JSON.parse(JSON.stringify(subject.free_time || subject.freeTime || {})));
    setFiles(
      (subject.documents || subject.docs || []).map((d) => ({
        file: { name: d.file_name || d.name, size: d.file_size || d.size },
        existing: true,
      }))
    );
    setShowModal(true);
  };

  // File handling
  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") setDragActive(true);
    else if (e.type === "dragleave") setDragActive(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files?.length > 0) handleFilesInput(Array.from(e.dataTransfer.files));
  };

  const handleFilesInput = (newFiles) => {
    const allowedTypes = ["application/pdf"];
    const validFiles = newFiles.filter((f) => allowedTypes.includes(f.type));
    if (validFiles.length < newFiles.length) {
      toast.error("Chỉ hỗ trợ file PDF");
    }
    setFiles((prev) => [...prev, ...validFiles.map((f) => ({ file: f }))]);
  };

  const removeFile = (idx) => setFiles((prev) => prev.filter((_, i) => i !== idx));

  const getFileIcon = (name) => {
    if (name.endsWith(".pdf")) return "📄";
    if (name.endsWith(".docx")) return "📝";
    if (name.endsWith(".pptx")) return "📊";
    if (name.endsWith(".txt")) return "📃";
    return "📁";
  };

  const formatFileSize = (bytes) => {
    if (typeof bytes === "string") return bytes;
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
    return (bytes / (1024 * 1024)).toFixed(1) + " MB";
  };

  // Free time grid
  const toggleTimeSlot = (day, time) => {
    if (isSlotOccupied(day, time)) return;
    setFreeTime((prev) => {
      const updated = { ...prev };
      if (!updated[day]) updated[day] = [];
      const idx = updated[day].indexOf(time);
      if (idx >= 0) {
        updated[day] = updated[day].filter((t) => t !== time);
        if (updated[day].length === 0) delete updated[day];
      } else {
        updated[day] = [...updated[day], time].sort();
      }
      return updated;
    });
  };

  const handleTimeMouseDown = (day, time) => {
    if (isSlotOccupied(day, time)) return;
    setIsDraggingTime(true);
    const isSelected = freeTime[day]?.includes(time);
    setDragMode(isSelected ? "remove" : "add");
    toggleTimeSlot(day, time);
  };

  const handleTimeMouseEnter = (day, time) => {
    if (!isDraggingTime || isSlotOccupied(day, time)) return;
    const isSelected = freeTime[day]?.includes(time);
    if (dragMode === "add" && !isSelected) toggleTimeSlot(day, time);
    if (dragMode === "remove" && isSelected) toggleTimeSlot(day, time);
  };

  const handleTimeMouseUp = () => setIsDraggingTime(false);

  useEffect(() => {
    document.addEventListener("mouseup", handleTimeMouseUp);
    return () => document.removeEventListener("mouseup", handleTimeMouseUp);
  }, []);

  const getTotalFreeHours = () => {
    return Object.values(freeTime).reduce((total, slots) => total + slots.length, 0);
  };

  // Submit – create or update subject via API
  const handleSubmit = async () => {
    if (!subjectName.trim()) return;
    setSubmitting(true);

    try {
      if (editingSubject) {
        await updateSubject(editingSubject, {
          name: subjectName,
          emoji: selectedEmoji,
          target_grade: targetGrade,
          end_date: endDate || null,
          free_time: freeTime,
        });
        toast.success("Đã cập nhật môn học!");
      } else {
        const pdfFile = files.find((f) => !f.existing && f.file instanceof File);
        const freshToken = getGoogleToken();
        await createSubject({
          name: subjectName,
          emoji: selectedEmoji,
          target_grade: targetGrade,
          end_date: endDate || null,
          free_time: freeTime,
          file: pdfFile?.file || null,
          google_access_token: freshToken?.google_access_token || null,
        });
        toast.success("Đã thêm môn học! Đang xử lý tài liệu...");
      }
      closeModal();
      await loadSubjects();
    } catch (err) {
      toast.error("Lỗi: " + err.message);
    } finally {
      setSubmitting(false);
    }
  };

  const deleteSubject = async (id) => {
    if (!window.confirm("Bạn có chắc muốn xóa môn học này?")) return;
    try {
      await deleteSubjectApi(id);
      setSubjects((prev) => prev.filter((s) => s.id !== id));
      toast.success("Đã xóa môn học");
    } catch (err) {
      toast.error("Lỗi khi xóa: " + err.message);
    }
  };

  const getGradeColor = (grade) => {
    if (grade >= 9) return "#059669";
    if (grade >= 7) return "#6366f1";
    if (grade >= 5) return "#d97706";
    return "#ef4444";
  };

  const getGradeLabel = (grade) => {
    if (grade >= 9) return "Xuất sắc";
    if (grade >= 8) return "Giỏi";
    if (grade >= 7) return "Khá";
    if (grade >= 5) return "Trung bình";
    return "Yếu";
  };

  const getDaysRemaining = (date) => {
    if (!date) return null;
    const diff = Math.ceil((new Date(date) - new Date()) / (1000 * 60 * 60 * 24));
    return diff;
  };

  const getSubjectFreeHours = (subject) => {
    const ft = subject.free_time || subject.freeTime || {};
    return Object.values(ft).reduce((t, s) => t + s.length, 0);
  };

  const getStatusBadge = (subject) => {
    const ing = subject.ingest_status;
    const plan = subject.plan_status;
    // if (ing === "processing" || plan === "generating") {
    //   return (
    //     <span className="idv2-status-badge idv2-status-processing">
    //       <Loader2 size={12} className="idv2-spin" /> Đang xử lý
    //     </span>
    //   );
    // }
    if (ing === "processing") {
      return (
        <span className="idv2-status-badge idv2-status-processing">
          <Loader2 size={12} className="idv2-spin" /> Đang xử lý data
        </span>
      );
    }
    if (plan === "generating") {
      return (
        <span className="idv2-status-badge idv2-status-completed">
          <Loader2 size={12} className="idv2-spin"/> Đang tạo kế hoạch học tập
        </span>
      );
    }
    if (plan === "completed") {
      return (
        <span className="idv2-status-badge idv2-status-completed">
          <CheckCircle2 size={12} /> Đã tạo lịch
        </span>
      );
    }
    if (ing === "failed" || plan === "failed") {
      return (
        <span className="idv2-status-badge idv2-status-failed">
          <AlertCircle size={12} /> Lỗi
        </span>
      );
    }
    return (
      <span className="idv2-status-badge idv2-status-pending">
        <Clock size={12} /> Chờ xử lý
      </span>
    );
  };

  return (
    <div className="import-docs-v2">
      {/* Header */}
      <div className="idv2-header">
        <div className="idv2-header-text">
          <h1>
            <GraduationCap size={30} /> Quản lý Môn học
          </h1>
          <p>Thêm môn học, import tài liệu PDF và thiết lập mục tiêu học tập cá nhân hóa</p>
        </div>
        <div className="idv2-header-stats">
          <div className="idv2-stat">
            <span className="idv2-stat-num">{subjects.length}</span>
            <span className="idv2-stat-label">Môn học</span>
          </div>
          <div className="idv2-stat">
            <span className="idv2-stat-num">
              {subjects.reduce((t, s) => t + (s.documents?.length || s.docs?.length || 0), 0)}
            </span>
            <span className="idv2-stat-label">Tài liệu</span>
          </div>
          <div className="idv2-stat">
            <span className="idv2-stat-num">
              {subjects.reduce((t, s) => t + getSubjectFreeHours(s), 0)}h
            </span>
            <span className="idv2-stat-label">Giờ rảnh/tuần</span>
          </div>
          <button className="idv2-refresh-btn" onClick={loadSubjects} title="Làm mới">
            <RefreshCw size={16} />
          </button>
        </div>
      </div>

      {/* Add Subject Button */}
      <button className="idv2-add-btn" onClick={() => setShowModal(true)}>
        <div className="idv2-add-btn-icon">
          <Plus size={32} strokeWidth={2.5} />
        </div>
        <div className="idv2-add-btn-text">
          <span className="idv2-add-btn-title">Thêm môn học mới</span>
          <span className="idv2-add-btn-desc">Import tài liệu PDF, đặt mục tiêu & lịch học</span>
        </div>
      </button>

      {/* Loading state */}
      {loading && (
        <div className="idv2-empty">
          <Loader2 size={32} className="idv2-spin" />
          <h3>Đang tải danh sách môn học...</h3>
        </div>
      )}

      {/* Subject List */}
      {!loading && subjects.length > 0 && (
        <div className="idv2-subjects-section">
          <h2 className="idv2-section-title">
            <BookOpen size={20} /> Môn học đã đăng ký ({subjects.length})
          </h2>
          <div className="idv2-subjects-grid">
            {subjects.map((subject) => {
              const daysLeft = getDaysRemaining(subject.end_date || subject.endDate);
              return (
                <div className="idv2-subject-card" key={subject.id}>
                  <div className="idv2-card-header">
                    <div className="idv2-card-emoji">{subject.emoji}</div>
                    <div className="idv2-card-title-area">
                      <h3>{subject.name}</h3>
                      <div className="idv2-card-meta-row">
                        <span className="idv2-card-date">
                          Thêm ngày {new Date(subject.created_at || subject.createdAt).toLocaleDateString("vi-VN")}
                        </span>
                        {getStatusBadge(subject)}
                      </div>
                    </div>
                    <div className="idv2-card-actions">
                      <button className="idv2-card-action-btn" title="Chỉnh sửa" onClick={() => openEditModal(subject)}>
                        <Edit3 size={15} />
                      </button>
                      <button className="idv2-card-action-btn idv2-card-action-danger" title="Xóa" onClick={() => deleteSubject(subject.id)}>
                        <Trash2 size={15} />
                      </button>
                    </div>
                  </div>

                  <div className="idv2-card-body">
                    <div className="idv2-card-metric">
                      <div className="idv2-metric-icon" style={{ background: `${getGradeColor(subject.target_grade || subject.targetGrade)}15`, color: getGradeColor(subject.target_grade || subject.targetGrade) }}>
                        <Target size={16} />
                      </div>
                      <div className="idv2-metric-info">
                        <span className="idv2-metric-label">Mục tiêu</span>
                        <span className="idv2-metric-value" style={{ color: getGradeColor(subject.target_grade || subject.targetGrade) }}>
                          {subject.target_grade || subject.targetGrade}/10 — {getGradeLabel(subject.target_grade || subject.targetGrade)}
                        </span>
                      </div>
                    </div>

                    <div className="idv2-card-metric">
                      <div className={`idv2-metric-icon ${daysLeft !== null && daysLeft <= 7 ? "idv2-metric-urgent" : "idv2-metric-calendar"}`}>
                        <CalendarDays size={16} />
                      </div>
                      <div className="idv2-metric-info">
                        <span className="idv2-metric-label">Kết thúc</span>
                        <span className="idv2-metric-value">
                          {(subject.end_date || subject.endDate)
                            ? new Date(subject.end_date || subject.endDate).toLocaleDateString("vi-VN", { day: "2-digit", month: "2-digit", year: "numeric" })
                            : "Chưa đặt"}
                          {daysLeft !== null && (
                            <span className={`idv2-days-badge ${daysLeft <= 7 ? "idv2-days-urgent" : ""}`}>
                              {daysLeft > 0 ? `còn ${daysLeft} ngày` : "Đã quá hạn"}
                            </span>
                          )}
                        </span>
                      </div>
                    </div>

                    <div className="idv2-card-metric">
                      <div className="idv2-metric-icon idv2-metric-time">
                        <Timer size={16} />
                      </div>
                      <div className="idv2-metric-info">
                        <span className="idv2-metric-label">Thời gian rảnh</span>
                        <span className="idv2-metric-value">
                          {getSubjectFreeHours(subject)}h/tuần
                          <span className="idv2-time-detail">
                            ({Object.keys(subject.free_time || subject.freeTime || {}).length} ngày)
                          </span>
                        </span>
                      </div>
                    </div>

                    <div className="idv2-card-docs">
                      <div className="idv2-docs-header">
                        <FileText size={14} />
                        <span>{subject.documents?.length || subject.docs?.length || 0} tài liệu</span>
                      </div>
                      <div className="idv2-docs-list">
                        {(subject.documents || subject.docs || []).slice(0, 3).map((doc, i) => (
                          <div className="idv2-doc-chip" key={i}>
                            <span>{getFileIcon(doc.file_name || doc.name)}</span>
                            <span className="idv2-doc-name">{doc.file_name || doc.name}</span>
                          </div>
                        ))}
                        {((subject.documents || subject.docs)?.length || 0) > 3 && (
                          <span className="idv2-docs-more">+{(subject.documents || subject.docs).length - 3} khác</span>
                        )}
                      </div>
                    </div>

                    <div className="idv2-card-schedule">
                      {DAYS_OF_WEEK.map((d) => {
                        const hours = (subject.free_time || subject.freeTime || {})[d.key]?.length || 0;
                        return (
                          <div className={`idv2-mini-day ${hours > 0 ? "idv2-mini-day-active" : ""}`} key={d.key}>
                            <span className="idv2-mini-day-label">{d.label}</span>
                            <span className="idv2-mini-day-hours">{hours > 0 ? `${hours}h` : "—"}</span>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {!loading && subjects.length === 0 && (
        <div className="idv2-empty">
          <div className="idv2-empty-icon">📚</div>
          <h3>Chưa có môn học nào</h3>
          <p>Bấm nút "Thêm môn học mới" để bắt đầu thiết lập lộ trình học tập</p>
        </div>
      )}

      {/* ===== MODAL ===== */}
      {showModal && (
        <div className="idv2-modal-overlay" onClick={closeModal}>
          <div className="idv2-modal" ref={modalRef} onClick={(e) => e.stopPropagation()}>
            <div className="idv2-modal-header">
              <h2>{editingSubject ? "✏️ Chỉnh sửa môn học" : "🎓 Thêm môn học mới"}</h2>
              <button className="idv2-modal-close" onClick={closeModal}>
                <X size={20} />
              </button>
            </div>

            <div className="idv2-modal-body">
              {/* Section 1: Subject Info */}
              <div className="idv2-form-section">
                <div className="idv2-form-section-header">
                  <div className="idv2-form-section-icon"><BookOpen size={18} /></div>
                  <span>Thông tin môn học</span>
                </div>
                <div className="idv2-subject-input-row">
                  <div className="idv2-emoji-selector">
                    <button className="idv2-emoji-btn" onClick={() => setShowEmojiPicker(!showEmojiPicker)}>
                      {selectedEmoji}
                      <ChevronDown size={12} />
                    </button>
                    {showEmojiPicker && (
                      <div className="idv2-emoji-dropdown">
                        {EMOJIS.map((e) => (
                          <button
                            key={e}
                            className={`idv2-emoji-option ${selectedEmoji === e ? "active" : ""}`}
                            onClick={() => { setSelectedEmoji(e); setShowEmojiPicker(false); }}
                          >
                            {e}
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                  <input
                    type="text"
                    className="idv2-input idv2-subject-name-input"
                    placeholder="Nhập tên môn học (VD: Toán cao cấp)"
                    value={subjectName}
                    onChange={(e) => setSubjectName(e.target.value)}
                    autoFocus
                  />
                </div>
              </div>

              {/* Section 2: File Upload */}
              <div className="idv2-form-section">
                <div className="idv2-form-section-header">
                  <div className="idv2-form-section-icon"><Upload size={18} /></div>
                  <span>Import tài liệu</span>
                </div>
                <div
                  className={`idv2-upload-zone ${dragActive ? "idv2-upload-active" : ""}`}
                  onDragEnter={handleDrag}
                  onDragLeave={handleDrag}
                  onDragOver={handleDrag}
                  onDrop={handleDrop}
                  onClick={() => fileInputRef.current?.click()}
                >
                  <input
                    ref={fileInputRef}
                    type="file"
                    multiple={false}
                    accept=".pdf"
                    style={{ display: "none" }}
                    onChange={(e) => handleFilesInput(Array.from(e.target.files))}
                  />
                  <Upload size={24} className="idv2-upload-icon-svg" />
                  <span className="idv2-upload-text">Kéo thả hoặc click để chọn file PDF</span>
                  <div className="idv2-upload-formats">
                    <span>PDF</span>
                  </div>
                </div>

                {files.length > 0 && (
                  <div className="idv2-file-list">
                    {files.map((f, idx) => (
                      <div className="idv2-file-item" key={idx}>
                        <span className="idv2-file-icon">{getFileIcon(f.file.name)}</span>
                        <div className="idv2-file-info">
                          <span className="idv2-file-name">{f.file.name}</span>
                          <span className="idv2-file-size">{formatFileSize(f.file.size)}</span>
                        </div>
                        {f.existing && <span className="idv2-file-badge">Đã upload</span>}
                        <button className="idv2-file-remove" onClick={(e) => { e.stopPropagation(); removeFile(idx); }}>
                          <X size={14} />
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Section 3: Target Grade */}
              <div className="idv2-form-section">
                <div className="idv2-form-section-header">
                  <div className="idv2-form-section-icon"><Target size={18} /></div>
                  <span>Mục tiêu điểm số</span>
                </div>
                <div className="idv2-grade-selector">
                  <div className="idv2-grade-display">
                    <div className="idv2-grade-circle" style={{ borderColor: getGradeColor(targetGrade) }}>
                      <span className="idv2-grade-number" style={{ color: getGradeColor(targetGrade) }}>{targetGrade}</span>
                      <span className="idv2-grade-total">/10</span>
                    </div>
                    <div className="idv2-grade-info">
                      <span className="idv2-grade-label" style={{ color: getGradeColor(targetGrade) }}>
                        {getGradeLabel(targetGrade)}
                      </span>
                      <span className="idv2-grade-desc">
                        {targetGrade >= 9 ? "Nỗ lực cao nhất, master kiến thức" :
                         targetGrade >= 8 ? "Nắm vững kiến thức, top lớp" :
                         targetGrade >= 7 ? "Hiểu bài tốt, hoàn thành đủ" :
                         targetGrade >= 5 ? "Đạt yêu cầu cơ bản" : "Cần cải thiện nhiều"}
                      </span>
                    </div>
                  </div>
                  <div className="idv2-grade-slider-container">
                    <input
                      type="range"
                      min="1"
                      max="10"
                      step="0.5"
                      value={targetGrade}
                      onChange={(e) => setTargetGrade(parseFloat(e.target.value))}
                      className="idv2-grade-slider"
                      style={{
                        background: `linear-gradient(to right, ${getGradeColor(targetGrade)} 0%, ${getGradeColor(targetGrade)} ${((targetGrade - 1) / 9) * 100}%, #e2e8f0 ${((targetGrade - 1) / 9) * 100}%, #e2e8f0 100%)`,
                      }}
                    />
                    <div className="idv2-grade-marks">
                      {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((n) => (
                        <span key={n} className={targetGrade >= n ? "active" : ""}>{n}</span>
                      ))}
                    </div>
                  </div>
                  <div className="idv2-grade-stars">
                    {[1, 2, 3, 4, 5].map((star) => (
                      <Star
                        key={star}
                        size={22}
                        className={`idv2-star ${targetGrade >= star * 2 ? "idv2-star-filled" : ""}`}
                        fill={targetGrade >= star * 2 ? "#fbbf24" : "none"}
                        color={targetGrade >= star * 2 ? "#fbbf24" : "#d1d5db"}
                        onClick={() => setTargetGrade(star * 2)}
                        style={{ cursor: "pointer" }}
                      />
                    ))}
                  </div>
                </div>
              </div>

              {/* Section 4: End Date */}
              <div className="idv2-form-section">
                <div className="idv2-form-section-header">
                  <div className="idv2-form-section-icon"><CalendarDays size={18} /></div>
                  <span>Thời gian kết thúc</span>
                </div>
                <div className="idv2-date-input-wrapper">
                  <Calendar size={18} className="idv2-date-icon" />
                  <input
                    type="date"
                    className="idv2-input idv2-date-input"
                    value={endDate}
                    onChange={(e) => setEndDate(e.target.value)}
                    min={new Date().toISOString().split("T")[0]}
                  />
                  {endDate && (
                    <span className="idv2-date-preview">
                      {new Date(endDate).toLocaleDateString("vi-VN", {
                        weekday: "long", day: "2-digit", month: "long", year: "numeric",
                      })}
                      {getDaysRemaining(endDate) > 0 && (
                        <> — <strong>còn {getDaysRemaining(endDate)} ngày</strong></>
                      )}
                    </span>
                  )}
                </div>
              </div>

              {/* Section 5: Free Time Grid */}
              <div className="idv2-form-section">
                <div className="idv2-form-section-header">
                  <div className="idv2-form-section-icon"><Clock size={18} /></div>
                  <span>Thời gian rảnh trong tuần</span>
                  {getTotalFreeHours() > 0 && (
                    <span className="idv2-free-hours-badge">{getTotalFreeHours()}h đã chọn</span>
                  )}
                </div>
                <p className="idv2-form-hint">
                  <AlertCircle size={13} />
                  Click hoặc kéo chuột để chọn khung giờ rảnh. Ô màu xám là lịch của môn khác.
                </p>
                <div className="idv2-time-grid-wrapper">
                  <div className="idv2-time-grid" onMouseLeave={() => setIsDraggingTime(false)}>
                    <div className="idv2-tg-corner"></div>
                    {DAYS_OF_WEEK.map((d) => (
                      <div className="idv2-tg-day-header" key={d.key}>{d.label}</div>
                    ))}
                    {TIME_SLOTS.map((time) => (
                      <div className="idv2-tg-row" key={`row-${time}`}>
                        <div className="idv2-tg-time-label">{time}</div>
                        {DAYS_OF_WEEK.map((d) => {
                          const selected = freeTime[d.key]?.includes(time);
                          const occupied = isSlotOccupied(d.key, time);
                          return (
                            <div
                              key={`${d.key}-${time}`}
                              className={`idv2-tg-cell ${selected ? "idv2-tg-selected" : ""} ${occupied ? "idv2-tg-occupied" : ""}`}
                              onMouseDown={() => handleTimeMouseDown(d.key, time)}
                              onMouseEnter={() => handleTimeMouseEnter(d.key, time)}
                              title={
                                occupied ? "Đã có lịch môn khác"
                                : selected ? `${d.label} ${time} — Đã chọn`
                                : `${d.label} ${time} — Click để chọn`
                              }
                            >
                              {selected && <CheckCircle2 size={12} />}
                              {occupied && <X size={10} className="idv2-tg-occupied-icon" />}
                            </div>
                          );
                        })}
                      </div>
                    ))}
                  </div>
                </div>
                <div className="idv2-time-legend">
                  <div className="idv2-legend-item">
                    <div className="idv2-legend-box idv2-legend-selected"></div>
                    <span>Đã chọn (rảnh)</span>
                  </div>
                  <div className="idv2-legend-item">
                    <div className="idv2-legend-box idv2-legend-occupied"></div>
                    <span>Lịch môn khác</span>
                  </div>
                  <div className="idv2-legend-item">
                    <div className="idv2-legend-box idv2-legend-empty"></div>
                    <span>Trống</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Modal Footer */}
            <div className="idv2-modal-footer">
              {!editingSubject && !googleToken && (
                <button
                  type="button"
                  className="idv2-btn-calendar"
                  onClick={() => {
                    requestCalendarToken();
                    // Re-check token after a short delay
                    setTimeout(() => setGoogleTokenState(getGoogleToken()), 3000);
                  }}
                  title="Cần để tự động thêm lịch học vào Google Calendar"
                >
                  📅 Kết nối Google Calendar
                </button>
              )}
              {!editingSubject && googleToken && (
                <span className="idv2-calendar-connected">✅ Google Calendar đã kết nối</span>
              )}
              <button className="idv2-btn-cancel" onClick={closeModal}>Hủy</button>
              <button className="idv2-btn-submit" onClick={handleSubmit} disabled={!subjectName.trim() || submitting}>
                {submitting ? (
                  <><Loader2 size={18} className="idv2-spin" /> Đang xử lý...</>
                ) : (
                  <><CheckCircle2 size={18} /> {editingSubject ? "Cập nhật môn học" : "Thêm môn học"}</>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ImportDocs;
