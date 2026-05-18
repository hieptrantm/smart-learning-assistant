import { useState, useEffect, useMemo } from "react";
import "./dashboard.css";
import {
  BookOpen,
  MessageSquare,
  FileText,
  TrendingUp,
  Clock,
  Award,
  Target,
  Calendar,
  CheckCircle2,
  XCircle,
  Loader2,
  AlertCircle,
} from "lucide-react";
import { usePlannerService } from "../../service/planner/usePlannerService";

const Dashboard = ({ user }) => {
  const [subjects, setSubjects] = useState([]);
  const [plansMap, setPlansMap] = useState({});
  const [loading, setLoading] = useState(true);

  const { getSubjects, getStudyPlan } = usePlannerService();

  // Load subjects + their plans
  useEffect(() => {
    if (!user) return;
    (async () => {
      try {
        setLoading(true);
        const subs = await getSubjects();
        setSubjects(subs);

        // Fetch plans for all subjects in parallel
        const planEntries = await Promise.allSettled(
          subs.map(async (s) => {
            try {
              const plan = await getStudyPlan(s.id);
              return [s.id, plan];
            } catch {
              return [s.id, null];
            }
          })
        );
        const map = {};
        planEntries.forEach((entry) => {
          if (entry.status === "fulfilled" && entry.value) {
            const [id, plan] = entry.value;
            map[id] = plan;
          }
        });
        setPlansMap(map);
      } catch (err) {
        console.error("Failed to load dashboard data:", err);
      } finally {
        setLoading(false);
      }
    })();
  }, [user, getSubjects, getStudyPlan]);

  // Aggregate all sessions across all subjects
  const allSessions = useMemo(() => {
    const sessions = [];
    Object.entries(plansMap).forEach(([subjectId, plan]) => {
      if (!plan?.sessions) return;
      const sub = subjects.find((s) => s.id === Number(subjectId));
      plan.sessions.forEach((sess) => {
        sessions.push({ ...sess, subjectName: sub?.name, subjectEmoji: sub?.emoji });
      });
    });
    return sessions;
  }, [plansMap, subjects]);

  // Stats
  const stats = useMemo(() => {
    const totalSubjects = subjects.length;
    const totalSessions = allSessions.length;
    const passedSessions = allSessions.filter((s) => s.learning_status === "passed");
    const failedSessions = allSessions.filter((s) => s.learning_status === "failed");
    const testedSessions = [...passedSessions, ...failedSessions];
    const totalDocuments = subjects.reduce((sum, s) => sum + (s.documents?.length || 0), 0);

    const scores = testedSessions.map((s) => s.score).filter((s) => s != null);
    const avgScore = scores.length > 0 ? Math.round(scores.reduce((a, b) => a + b, 0) / scores.length) : 0;

    return {
      totalSubjects,
      totalSessions,
      totalTested: testedSessions.length,
      totalPassed: passedSessions.length,
      totalFailed: failedSessions.length,
      totalDocuments,
      avgScore,
    };
  }, [subjects, allSessions]);

  // Per-subject progress
  const subjectProgress = useMemo(() => {
    return subjects.map((sub) => {
      const plan = plansMap[sub.id];
      const sessions = plan?.sessions || [];
      const total = sessions.length;
      const passed = sessions.filter((s) => s.learning_status === "passed").length;
      const failed = sessions.filter((s) => s.learning_status === "failed").length;
      const notStarted = sessions.filter((s) => s.learning_status === "not_started").length;
      const progress = total > 0 ? Math.round((passed / total) * 100) : 0;
      const scores = sessions.map((s) => s.score).filter((s) => s != null);
      const avgScore = scores.length > 0 ? Math.round(scores.reduce((a, b) => a + b, 0) / scores.length) : null;

      return {
        ...sub,
        totalSessions: total,
        passed,
        failed,
        notStarted,
        progress,
        avgScore,
        docCount: sub.documents?.length || 0,
      };
    });
  }, [subjects, plansMap]);

  // Upcoming sessions (today or future, not_started)
  const upcomingSessions = useMemo(() => {
    const today = new Date().toISOString().split("T")[0];
    return allSessions
      .filter((s) => s.session_date >= today && s.learning_status === "not_started")
      .sort((a, b) => a.session_date.localeCompare(b.session_date) || a.start_time.localeCompare(b.start_time))
      .slice(0, 5);
  }, [allSessions]);

  // Recent test results (passed or failed, sorted by date desc)
  const recentTests = useMemo(() => {
    return allSessions
      .filter((s) => s.learning_status === "passed" || s.learning_status === "failed")
      .sort((a, b) => b.session_date.localeCompare(a.session_date))
      .slice(0, 5);
  }, [allSessions]);

  const SUBJECT_COLORS = ["#003087", "#10b981", "#f59e0b", "#ec4899", "#3b82f6", "#0077cc", "#ef4444", "#14b8a6"];

  if (loading) {
    return (
      <div className="dashboard">
        <div className="dashboard-loading">
          <Loader2 size={32} className="spin-icon" />
          <span>Đang tải dữ liệu...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="dashboard">
      {/* Welcome Section */}
      <div className="dashboard-welcome">
        <div className="welcome-text">
          <h1>Chào mừng trở lại, {user?.username || "Learner"}! 👋</h1>
          <p>Theo dõi tiến độ học tập và tiếp tục hành trình của bạn.</p>
        </div>
        <div className="welcome-date">
          <Calendar size={18} />
          <span>{new Date().toLocaleDateString("vi-VN", { weekday: "long", year: "numeric", month: "long", day: "numeric" })}</span>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="dashboard-stats">
        <div className="stat-card stat-card-purple">
          <div className="stat-card-icon"><BookOpen size={24} /></div>
          <div className="stat-card-info">
            <span className="stat-card-value">{stats.totalSubjects}</span>
            <span className="stat-card-label">Môn học</span>
          </div>
        </div>
        <div className="stat-card stat-card-green">
          <div className="stat-card-icon"><FileText size={24} /></div>
          <div className="stat-card-info">
            <span className="stat-card-value">{stats.totalDocuments}</span>
            <span className="stat-card-label">Tài liệu</span>
          </div>
        </div>
        <div className="stat-card stat-card-amber">
          <div className="stat-card-icon"><MessageSquare size={24} /></div>
          <div className="stat-card-info">
            <span className="stat-card-value">{stats.totalTested}</span>
            <span className="stat-card-label">Bài kiểm tra</span>
          </div>
        </div>
        <div className="stat-card stat-card-blue">
          <div className="stat-card-icon"><TrendingUp size={24} /></div>
          <div className="stat-card-info">
            <span className="stat-card-value">{stats.totalTested > 0 ? `${stats.avgScore}%` : "—"}</span>
            <span className="stat-card-label">Điểm trung bình</span>
          </div>
        </div>
      </div>

      {/* Main Grid */}
      <div className="dashboard-grid">
        {/* Subject Progress */}
        <div className="dashboard-card">
          <div className="card-header">
            <h3><Target size={18} /> Tiến độ môn học</h3>
          </div>
          <div className="card-body">
            {subjectProgress.length === 0 ? (
              <div className="card-empty">
                <AlertCircle size={20} />
                <span>Chưa có môn học nào.</span>
              </div>
            ) : (
              subjectProgress.map((sub, idx) => (
                <div className="progress-item" key={sub.id}>
                  <div className="progress-item-header">
                    <span className="progress-course-name">
                      {sub.emoji} {sub.name}
                    </span>
                    <span className="progress-percentage">{sub.progress}%</span>
                  </div>
                  <div className="progress-bar-container">
                    <div
                      className="progress-bar-fill"
                      style={{ width: `${sub.progress}%`, background: SUBJECT_COLORS[idx % SUBJECT_COLORS.length] }}
                    />
                  </div>
                  <div className="progress-detail-row">
                    <span className="progress-detail">
                      <CheckCircle2 size={12} /> {sub.passed} đạt
                    </span>
                    <span className="progress-detail progress-detail-fail">
                      <XCircle size={12} /> {sub.failed} chưa đạt
                    </span>
                    <span className="progress-detail">
                      {sub.notStarted} chưa học / {sub.totalSessions} buổi
                    </span>
                  </div>
                  {sub.avgScore != null && (
                    <span className="progress-avg-score">
                      Điểm TB: <strong>{sub.avgScore}%</strong>
                    </span>
                  )}
                  <div className="progress-meta">
                    <span className={`status-badge status-${sub.plan_status}`}>
                      {sub.plan_status === "completed" ? "Có lộ trình" : sub.plan_status === "generating" ? "Đang tạo..." : sub.plan_status === "pending" ? "Chờ tạo" : "Lỗi"}
                    </span>
                    <span className="progress-docs">
                      <FileText size={12} /> {sub.docCount} tài liệu
                    </span>
                    {sub.target_grade && (
                      <span className="progress-target">
                        🎯 Mục tiêu: {sub.target_grade}
                      </span>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Upcoming Sessions */}
        <div className="dashboard-card">
          <div className="card-header">
            <h3><Clock size={18} /> Buổi học sắp tới</h3>
          </div>
          <div className="card-body">
            {upcomingSessions.length === 0 ? (
              <div className="card-empty">
                <CheckCircle2 size={20} />
                <span>Không có buổi học nào sắp tới.</span>
              </div>
            ) : (
              upcomingSessions.map((sess) => (
                <div className="task-item" key={sess.id}>
                  <div className="task-date-badge">
                    <span className="task-date-day">
                      {new Date(sess.session_date + "T00:00:00").getDate()}
                    </span>
                    <span className="task-date-month">
                      Th{new Date(sess.session_date + "T00:00:00").getMonth() + 1}
                    </span>
                  </div>
                  <div className="task-info">
                    <span className="task-name">
                      {sess.subjectEmoji} {sess.title || sess.subjectName}
                    </span>
                    <span className="task-deadline">
                      <Clock size={12} /> {sess.start_time} - {sess.end_time}
                    </span>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Test Results */}
        <div className="dashboard-card dashboard-card-wide">
          <div className="card-header">
            <h3><Award size={18} /> Kết quả kiểm tra gần đây</h3>
          </div>
          <div className="card-body">
            {recentTests.length === 0 ? (
              <div className="card-empty">
                <AlertCircle size={20} />
                <span>Chưa có bài kiểm tra nào.</span>
              </div>
            ) : (
              recentTests.map((test) => {
                const score = test.score != null ? Math.round(test.score) : null;
                const passed = test.learning_status === "passed";
                return (
                  <div className="test-result-item" key={test.id}>
                    <div className="test-result-info">
                      <span className="test-result-name">
                        {test.subjectEmoji} {test.title || test.subjectName}
                      </span>
                      <span className="test-result-date">
                        {new Date(test.session_date + "T00:00:00").toLocaleDateString("vi-VN")}
                      </span>
                    </div>
                    <div className="test-result-score">
                      {score != null ? (
                        <span className={`score-value ${score >= 80 ? "score-high" : score >= 60 ? "score-mid" : "score-low"}`}>
                          {score}%
                        </span>
                      ) : (
                        <span className={`score-badge ${passed ? "badge-pass" : "badge-fail"}`}>
                          {passed ? "Đạt" : "Chưa đạt"}
                        </span>
                      )}
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
