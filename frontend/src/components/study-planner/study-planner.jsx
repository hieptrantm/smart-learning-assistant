import { useState, useEffect, useCallback } from "react";
import "./study-planner.css";
import {
  CalendarCheck,
  Clock,
  Target,
  AlertTriangle,
  CheckCircle2,
  Calendar,
  Mail,
  BookOpen,
  Loader2,
  RefreshCw,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import { usePlannerService } from "../../service/planner/usePlannerService";
import toast from "react-hot-toast";

const StudyPlanner = ({ user }) => {
  const [subjects, setSubjects] = useState([]);
  const [plans, setPlans] = useState({});  // subjectId → plan data
  const [loading, setLoading] = useState(true);
  const [expandedSubject, setExpandedSubject] = useState(null);

  const { getSubjects, getStudyPlan, syncCalendar } = usePlannerService();

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      const subs = await getSubjects();
      setSubjects(subs);

      // Load plans for subjects that have completed plans
      const planMap = {};
      for (const s of subs) {
        if (s.plan_status === "completed") {
          try {
            const plan = await getStudyPlan(s.id);
            planMap[s.id] = plan;
          } catch (e) {
            // Plan not ready yet
          }
        }
      }
      setPlans(planMap);
    } catch (err) {
      console.error("Failed to load planner data:", err);
    } finally {
      setLoading(false);
    }
  }, [getStudyPlan, getSubjects]);

  useEffect(() => {
    if (user) loadData();
  }, [user, loadData]);

  // Group sessions by week for a subject's plan
  const getWeekSchedule = (subjectId) => {
    const plan = plans[subjectId];
    if (!plan || !plan.sessions) return [];

    const dayMap = {};
    for (const s of plan.sessions) {
      const d = new Date(s.session_date);
      const dayLabel = d.toLocaleDateString("vi-VN", { weekday: "long", day: "2-digit", month: "2-digit" });
      if (!dayMap[s.session_date]) {
        dayMap[s.session_date] = { day: dayLabel, date: s.session_date, tasks: [] };
      }
      dayMap[s.session_date].tasks.push({
        time: `${s.start_time} - ${s.end_time}`,
        title: s.title || "Buổi học",
        content: s.content || "",
        status: s.status,
      });
    }

    return Object.values(dayMap).sort((a, b) => a.date.localeCompare(b.date));
  };

  const handleSyncCalendar = async (subjectId) => {
    const accessToken = prompt("Nhập Google Access Token để đồng bộ Calendar:");
    if (accessToken === null) return;

    const refreshToken = prompt("Nhập Google Refresh Token (có thể để trống nếu token access còn hạn):") || undefined;

    try {
      const result = await syncCalendar(subjectId, {
        google_access_token: accessToken || undefined,
        google_refresh_token: refreshToken,
      });

      if (result.success_count > 0) {
        toast.success(`Đã đồng bộ ${result.success_count} buổi học lên Google Calendar!`);
      } else {
        toast.error("Không tạo được sự kiện nào trên Google Calendar.");
      }
      await loadData();
    } catch (err) {
      toast.error("Lỗi đồng bộ: " + err.message);
    }
  };

  const getStatusInfo = (subject) => {
    if (subject.plan_status === "completed") {
      const plan = plans[subject.id];
      const totalSessions = plan?.sessions?.length || 0;
      const completed = plan?.sessions?.filter(s => s.status === "completed").length || 0;
      const progress = totalSessions > 0 ? Math.round((completed / totalSessions) * 100) : 0;
      return { status: "on-track", progress, totalSessions };
    }
    if (subject.plan_status === "generating" || subject.ingest_status === "processing") {
      return { status: "processing", progress: 0, totalSessions: 0 };
    }
    if (subject.plan_status === "failed" || subject.ingest_status === "failed") {
      return { status: "failed", progress: 0, totalSessions: 0 };
    }
    return { status: "pending", progress: 0, totalSessions: 0 };
  };

  return (
    <div className="study-planner">
      {/* Header */}
      <div className="planner-header">
        <div className="planner-header-left">
          <h1>
            <CalendarCheck size={28} /> Study Planner
          </h1>
          <p>Quản lý lộ trình học tập cá nhân hóa, đồng bộ với Google Calendar</p>
        </div>
        <div className="planner-header-actions">
          <button className="planner-btn planner-btn-outline" onClick={loadData}>
            <RefreshCw size={16} /> Làm mới
          </button>
        </div>
      </div>

      {loading && (
        <div className="planner-loading">
          <Loader2 size={32} className="planner-spin" />
          <span>Đang tải lộ trình học tập...</span>
        </div>
      )}

      {!loading && subjects.length === 0 && (
        <div className="planner-empty">
          <BookOpen size={48} />
          <h3>Chưa có môn học nào</h3>
          <p>Hãy vào trang "Quản lý Môn học" để thêm môn học và import tài liệu.</p>
        </div>
      )}

      {!loading && (
        <div className="planner-content">
          {/* Subject Goals */}
          <div className="planner-section">
            <h2 className="section-heading">
              <Target size={20} /> Môn học & Lộ trình
            </h2>
            <div className="goals-grid">
              {subjects.map((subject) => {
                const info = getStatusInfo(subject);
                const isExpanded = expandedSubject === subject.id;
                const schedule = isExpanded ? getWeekSchedule(subject.id) : [];

                return (
                  <div className={`goal-card goal-card-${info.status}`} key={subject.id}>
                    <div className="goal-card-header">
                      <div className="goal-subject">
                        <span>{subject.emoji}</span>
                        <span>{subject.name}</span>
                      </div>
                      <div className={`goal-status goal-status-${info.status}`}>
                        {info.status === "on-track" && <><CheckCircle2 size={14} /> Sẵn sàng</>}
                        {info.status === "processing" && <><Loader2 size={14} className="planner-spin" /> Đang tạo...</>}
                        {info.status === "failed" && <><AlertTriangle size={14} /> Lỗi</>}
                        {info.status === "pending" && <><Clock size={14} /> Chờ xử lý</>}
                      </div>
                    </div>

                    <h3 className="goal-target">
                      Mục tiêu: {subject.target_grade}/10
                    </h3>

                    {info.status === "on-track" && (
                      <div className="goal-progress-bar">
                        <div className="goal-progress-fill" style={{ width: `${info.progress}%` }}></div>
                      </div>
                    )}

                    <div className="goal-meta">
                      {subject.end_date && (
                        <span>
                          <Calendar size={12} /> Hạn: {new Date(subject.end_date).toLocaleDateString("vi-VN")}
                        </span>
                      )}
                      <span>
                        <BookOpen size={12} /> {info.totalSessions} buổi học
                      </span>
                    </div>

                    <div className="goal-actions">
                      {subject.plan_status === "completed" && (
                        <>
                          <button
                            className="goal-action-btn"
                            title="Xem lịch học"
                            onClick={() => setExpandedSubject(isExpanded ? null : subject.id)}
                          >
                            {isExpanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                          </button>
                          <button
                            className="goal-action-btn"
                            title="Đồng bộ Google Calendar"
                            onClick={() => handleSyncCalendar(subject.id)}
                          >
                            <Calendar size={14} />
                          </button>
                        </>
                      )}
                    </div>

                    {/* Expanded schedule */}
                    {isExpanded && schedule.length > 0 && (
                      <div className="goal-schedule-expanded">
                        {schedule.slice(0, 14).map((day, idx) => (
                          <div className="schedule-day-inline" key={idx}>
                            <div className="schedule-day-header-inline">{day.day}</div>
                            {day.tasks.map((task, tidx) => (
                              <div className="schedule-task-inline" key={tidx}>
                                <span className="schedule-time-inline">{task.time}</span>
                                <div className="schedule-task-content">
                                  <span className="schedule-task-title">{task.title}</span>
                                  {task.content && (
                                    <span className="schedule-task-desc">{task.content.substring(0, 120)}...</span>
                                  )}
                                </div>
                              </div>
                            ))}
                          </div>
                        ))}
                        {schedule.length > 14 && (
                          <div className="schedule-more">+{schedule.length - 14} ngày nữa...</div>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}

      {/* Notification Settings */}
      <div className="planner-notifications">
        <div className="notif-content">
          <Mail size={20} />
          <div>
            <strong>Nhắc nhở qua Google Calendar</strong>
            <p>Khi đồng bộ, hệ thống sẽ tự động cài thông báo trước nửa ngày cho mỗi buổi học.</p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default StudyPlanner;
