import { useState } from "react";
import "./homepage.css";
import {
  MessageSquare,
  CalendarCheck,
  FileText,
  Upload,
  BarChart3,
  Brain,
  Clock,
  Mail,
  BookOpen,
  Target,
  Sparkles,
  ArrowRight,
  GraduationCap,
  Zap,
  Shield,
  CheckCircle,
  TrendingUp,
} from "lucide-react";

const Homepage = ({ onNavigate, user }) => {
  const [hoveredCard, setHoveredCard] = useState(null);

  const features = [
    {
      id: "chatbot",
      icon: <MessageSquare size={32} />,
      title: "Chatbot Giảng bài & Hỏi đáp",
      description:
        "AI giảng bài trực tiếp từ slide PDF môn học của bạn. Hỏi bất kỳ điều gì — chatbot giải thích, ví dụ minh họa và kiểm tra mức độ hiểu bài sau mỗi buổi.",
      highlights: ["Giảng bài tương tác", "Hỏi đáp thông minh", "Dựa trên tài liệu PDF"],
      color: "#003087",
      gradient: "linear-gradient(135deg, #003087 0%, #0077cc 100%)",
      tab: "Chatbot",
    },
    {
      id: "planner",
      icon: <CalendarCheck size={32} />,
      title: "Lộ trình học cá nhân hóa",
      description:
        "Hệ thống tự động xây dựng kế hoạch học tập phù hợp với thời gian rảnh và mục tiêu điểm số. Đồng bộ Google Calendar và gửi nhắc nhở qua Gmail.",
      highlights: ["Cá nhân hóa AI", "Google Calendar", "Nhắc nhở Gmail"],
      color: "#10b981",
      gradient: "linear-gradient(135deg, #10b981 0%, #059669 100%)",
      tab: "Planner",
    },
    {
      id: "quiz",
      icon: <FileText size={32} />,
      title: "Kiểm tra & Đánh giá tiến độ",
      description:
        "Sau mỗi buổi học, chatbot tạo bài quiz để đánh giá mức độ nắm bài. Nếu chưa đạt yêu cầu, lộ trình tự động điều chỉnh để ôn tập lại.",
      highlights: ["Quiz tự động", "Chấm điểm AI", "Tái ôn khi cần"],
      color: "#f59e0b",
      gradient: "linear-gradient(135deg, #f59e0b 0%, #d97706 100%)",
      tab: "Chatbot",
    },
    {
      id: "import",
      icon: <Upload size={32} />,
      title: "Tải lên tài liệu PDF",
      description:
        "Nạp giáo trình, slide bài giảng PDF vào hệ thống. AI tự động xử lý, phân tích cấu trúc và sẵn sàng để chatbot giảng bài theo từng chương.",
      highlights: ["Slide PDF bài giảng", "Xử lý tự động", "Phân tích theo chương"],
      color: "#0077cc",
      gradient: "linear-gradient(135deg, #0055a5 0%, #00adee 100%)",
      tab: "Import",
    },
    {
      id: "dashboard",
      icon: <BarChart3 size={32} />,
      title: "Thống kê tiến độ học tập",
      description:
        "Theo dõi lịch sử buổi học, điểm kiểm tra từng môn và tỷ lệ hoàn thành lộ trình. Biết rõ điểm mạnh — điểm yếu để tập trung đúng chỗ.",
      highlights: ["Lịch sử buổi học", "Biểu đồ điểm số", "Tiến độ môn học"],
      color: "#3b82f6",
      gradient: "linear-gradient(135deg, #3b82f6 0%, #2563eb 100%)",
      tab: "Dashboard",
    },
  ];

  const stats = [
    { icon: <BookOpen size={24} />, label: "Định dạng hỗ trợ", value: "PDF Bài giảng" },
    { icon: <Brain size={24} />, label: "Công nghệ", value: "RAG + LLM" },
    { icon: <Target size={24} />, label: "Lộ trình", value: "Cá nhân hóa" },
    { icon: <Clock size={24} />, label: "Nhắc nhở", value: "Google Calendar & Gmail" },
  ];

  return (
    <div className="homepage">
      {/* Hero Section */}
      <section className="hero-section">
        <div className="hero-bg-decoration">
          <div className="hero-circle hero-circle-1"></div>
          <div className="hero-circle hero-circle-2"></div>
          <div className="hero-circle hero-circle-3"></div>
        </div>
        <div className="hero-content">
          <div className="hero-badge">
            <Sparkles size={16} />
            <span>Trợ lý học tập thông minh tích hợp AI</span>
          </div>
          <h1 className="hero-title">
            <span className="hero-title-gradient">Smart Learning</span>
            <br />
            Assistant
          </h1>
          <p className="hero-subtitle">
            Học từ chính <strong>bài giảng</strong> của bạn — AI giảng bài, hỏi đáp,
            xây dựng <strong>lộ trình học cá nhân hóa</strong> và kiểm tra kết quả sau
            mỗi buổi học để giúp bạn đạt điểm mục tiêu.
          </p>
          <div className="hero-actions">
            {user ? (
              <button
                className="hero-btn hero-btn-primary"
                onClick={() => onNavigate("Chatbot")}
              >
                <MessageSquare size={20} />
                Bắt đầu học ngay
                <ArrowRight size={18} />
              </button>
            ) : (
              <button
                className="hero-btn hero-btn-primary"
                onClick={() => (window.location.href = "/sign-in")}
              >
                <GraduationCap size={20} />
                Đăng nhập để bắt đầu
                <ArrowRight size={18} />
              </button>
            )}
            <button
              className="hero-btn hero-btn-secondary"
              onClick={() =>
                document
                  .getElementById("features-section")
                  ?.scrollIntoView({ behavior: "smooth" })
              }
            >
              Khám phá tính năng
            </button>
          </div>
        </div>

        {/* Hero Illustration */}
        <div className="hero-illustration">
          <div className="hero-card hero-card-chat">
            <MessageSquare size={24} className="hero-card-icon" />
            <div className="hero-card-text">
              <span className="hero-card-title">Chatbot Giảng bài</span>
              <span className="hero-card-desc">AI giải thích từ slide PDF</span>
            </div>
          </div>
          <div className="hero-card hero-card-plan">
            <CalendarCheck size={24} className="hero-card-icon" />
            <div className="hero-card-text">
              <span className="hero-card-title">Lộ trình cá nhân</span>
              <span className="hero-card-desc">Đã đồng bộ Google Calendar</span>
            </div>
          </div>
          <div className="hero-card hero-card-test">
            <CheckCircle size={24} className="hero-card-icon" />
            <div className="hero-card-text">
              <span className="hero-card-title">Kết quả kiểm tra</span>
              <span className="hero-card-desc">Đạt 85% — lộ trình tiếp theo sẵn sàng</span>
            </div>
          </div>
        </div>
      </section>

      {/* Stats Bar */}
      <section className="stats-bar">
        {stats.map((stat, index) => (
          <div className="stat-item" key={index}>
            <div className="stat-icon">{stat.icon}</div>
            <div className="stat-info">
              <span className="stat-value">{stat.value}</span>
              <span className="stat-label">{stat.label}</span>
            </div>
          </div>
        ))}
      </section>

      {/* Features Section */}
      <section className="features-section" id="features-section">
        <div className="section-header">
          <h2 className="section-title">Tính năng cốt lõi</h2>
          <p className="section-subtitle">
            Toàn bộ công cụ học tập thông minh bạn cần — từ tiếp nhận tài liệu đến đánh giá kết quả
          </p>
        </div>

        <div className="features-grid">
          {features.map((feature) => (
            <div
              className={`feature-card ${
                hoveredCard === feature.id ? "feature-card-hovered" : ""
              }`}
              key={feature.id}
              onMouseEnter={() => setHoveredCard(feature.id)}
              onMouseLeave={() => setHoveredCard(null)}
              onClick={() => onNavigate(feature.tab)}
            >
              <div
                className="feature-icon-wrapper"
                style={{ background: feature.gradient }}
              >
                {feature.icon}
              </div>
              <h3 className="feature-title">{feature.title}</h3>
              <p className="feature-description">{feature.description}</p>
              <div className="feature-highlights">
                {feature.highlights.map((h, i) => (
                  <span
                    className="feature-tag"
                    key={i}
                    style={{
                      backgroundColor: `${feature.color}15`,
                      color: feature.color,
                    }}
                  >
                    {h}
                  </span>
                ))}
              </div>
              <div className="feature-cta" style={{ color: feature.color }}>
                <span>Khám phá</span>
                <ArrowRight size={16} />
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* How It Works */}
      <section className="how-it-works">
        <div className="section-header">
          <h2 className="section-title">Cách hoạt động</h2>
          <p className="section-subtitle">
            Chỉ 4 bước để SLA trở thành gia sư AI riêng của bạn
          </p>
        </div>
        <div className="steps-grid">
          <div className="step-card">
            <div className="step-number">1</div>
            <div className="step-icon">
              <Upload size={28} />
            </div>
            <h3>Tải lên PDF bài giảng</h3>
            <p>
              Nạp slide, giáo trình PDF vào hệ thống. AI tự động phân tích và
              xây dựng cơ sở kiến thức cho từng môn học.
            </p>
          </div>
          <div className="step-connector">
            <ArrowRight size={24} />
          </div>
          <div className="step-card">
            <div className="step-number">2</div>
            <div className="step-icon">
              <CalendarCheck size={28} />
            </div>
            <h3>AI tạo lộ trình học</h3>
            <p>
              Study Planner xây dựng lịch học cá nhân hóa theo thời gian rảnh
              và mục tiêu điểm. Đồng bộ Google Calendar tự động.
            </p>
          </div>
          <div className="step-connector">
            <ArrowRight size={24} />
          </div>
          <div className="step-card">
            <div className="step-number">3</div>
            <div className="step-icon">
              <MessageSquare size={28} />
            </div>
            <h3>Học cùng Chatbot AI</h3>
            <p>
              Chatbot giảng bài từng chủ đề trong slide PDF, giải đáp thắc mắc
              và ôn tập kiến thức theo lộ trình đã lên.
            </p>
          </div>
          <div className="step-connector">
            <ArrowRight size={24} />
          </div>
          <div className="step-card">
            <div className="step-number">4</div>
            <div className="step-icon">
              <TrendingUp size={28} />
            </div>
            <h3>Quiz & Điều chỉnh lộ trình</h3>
            <p>
              Cuối buổi học, AI kiểm tra nhanh mức độ hiểu bài. Nếu chưa đạt,
              lộ trình tự động cập nhật để ôn luyện thêm.
            </p>
          </div>
        </div>
      </section>

      {/* Bottom CTA */}
      <section className="bottom-cta">
        <div className="cta-content">
          <div className="cta-decoration">
            <GraduationCap size={40} />
          </div>
          <h2>Sẵn sàng học thông minh hơn?</h2>
          <p>
            Tải lên slide bài giảng PDF — SLA sẽ tự động xây dựng lộ trình học
            và trở thành gia sư AI riêng của bạn.
          </p>
          <div className="cta-features">
            <div className="cta-feature">
              <BookOpen size={18} />
              <span>Học từ tài liệu PDF</span>
            </div>
            <div className="cta-feature">
              <Target size={18} />
              <span>Lộ trình cá nhân hóa</span>
            </div>
            <div className="cta-feature">
              <Mail size={18} />
              <span>Nhắc nhở qua Gmail</span>
            </div>
          </div>
          {user ? (
            <button
              className="hero-btn hero-btn-primary cta-btn"
              onClick={() => onNavigate("Import")}
            >
              <Upload size={20} />
              Tải lên tài liệu ngay
              <ArrowRight size={18} />
            </button>
          ) : (
            <button
              className="hero-btn hero-btn-primary cta-btn"
              onClick={() => (window.location.href = "/sign-up")}
            >
              <GraduationCap size={20} />
              Đăng ký miễn phí
              <ArrowRight size={18} />
            </button>
          )}
        </div>
      </section>

      {/* Footer */}
      <footer className="homepage-footer">
        <div className="footer-content">
          <div className="footer-brand">
            <img src="/sla_g.png" alt="SLA" style={{ height: "32px", width: "auto" }} />
          </div>
          <p className="footer-text">
            © 2026 Smart Learning Assistant — UET VNU-HN. Trợ lý học tập AI thế hệ mới.
          </p>
        </div>
      </footer>
    </div>
  );
};

export default Homepage;
