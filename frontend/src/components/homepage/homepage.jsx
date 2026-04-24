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
} from "lucide-react";

const Homepage = ({ onNavigate, user }) => {
  const [hoveredCard, setHoveredCard] = useState(null);

  const features = [
    {
      id: "chatbot",
      icon: <MessageSquare size={32} />,
      title: "Chatbot RAG",
      description:
        "Trả lời câu hỏi dựa trên tài liệu môn học. Hỗ trợ tóm tắt, giải thích chi tiết, đưa ví dụ và sinh bài tập.",
      highlights: ["Trích dẫn nguồn", "Giảm hallucination", "PDF/DOCX/PPTX"],
      color: "#6366f1",
      gradient: "linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%)",
      tab: "Chatbot",
    },
    {
      id: "planner",
      icon: <CalendarCheck size={32} />,
      title: "Study Planner",
      description:
        "Tự động tạo lộ trình học tập cá nhân hóa, đồng bộ Google Calendar và gửi nhắc nhở qua Gmail.",
      highlights: ["Google Calendar", "Nhắc nhở Gmail", "Cảnh báo tiến độ"],
      color: "#10b981",
      gradient: "linear-gradient(135deg, #10b981 0%, #059669 100%)",
      tab: "Planner",
    },
    {
      id: "test",
      icon: <FileText size={32} />,
      title: "Test Generator",
      description:
        "Tạo bài kiểm tra trắc nghiệm & tự luận theo các cấp độ. LLM tự động điều chỉnh tiến độ dựa trên kết quả.",
      highlights: ["Đa cấp độ", "Chấm tự động", "Phân tích điểm mạnh/yếu"],
      color: "#f59e0b",
      gradient: "linear-gradient(135deg, #f59e0b 0%, #d97706 100%)",
      tab: "Tests",
    },
    {
      id: "import",
      icon: <Upload size={32} />,
      title: "Import Tài liệu",
      description:
        "Tải lên tài liệu PDF, DOCX, PPTX, TXT. Tự động parsing, OCR, chunking và index vào vector database.",
      highlights: ["OCR tự động", "Chunking thông minh", "Qdrant indexing"],
      color: "#ec4899",
      gradient: "linear-gradient(135deg, #ec4899 0%, #db2777 100%)",
      tab: "Import",
    },
    {
      id: "dashboard",
      icon: <BarChart3 size={32} />,
      title: "Dashboard Học tập",
      description:
        "Theo dõi tiến độ, lịch sử câu hỏi, thống kê kết quả kiểm tra và báo cáo qua email.",
      highlights: ["Thống kê chi tiết", "Báo cáo email", "Tiến độ realtime"],
      color: "#3b82f6",
      gradient: "linear-gradient(135deg, #3b82f6 0%, #2563eb 100%)",
      tab: "Dashboard",
    },
  ];

  const stats = [
    { icon: <Brain size={24} />, label: "AI-Powered", value: "GPT-4 / Gemini" },
    { icon: <BookOpen size={24} />, label: "Định dạng hỗ trợ", value: "PDF, DOCX, PPTX, TXT" },
    { icon: <Target size={24} />, label: "Cá nhân hóa", value: "Adaptive Learning" },
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
            <span>Powered by AI & RAG Technology</span>
          </div>
          <h1 className="hero-title">
            <span className="hero-title-gradient">Smart Learning</span>
            <br />
            Agent
          </h1>
          <p className="hero-subtitle">
            Hệ thống trợ lý học tập thông minh dành cho học sinh, sinh viên và
            người tự học. Kết hợp <strong>Chatbot RAG</strong>,{" "}
            <strong>Study Planner</strong> và <strong>Test Generator</strong> giúp
            bạn học hiệu quả hơn.
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
              <span className="hero-card-title">Chatbot RAG</span>
              <span className="hero-card-desc">Hỏi đáp thông minh</span>
            </div>
          </div>
          <div className="hero-card hero-card-plan">
            <CalendarCheck size={24} className="hero-card-icon" />
            <div className="hero-card-text">
              <span className="hero-card-title">Study Planner</span>
              <span className="hero-card-desc">Lộ trình cá nhân hóa</span>
            </div>
          </div>
          <div className="hero-card hero-card-test">
            <FileText size={24} className="hero-card-icon" />
            <div className="hero-card-text">
              <span className="hero-card-title">Test Generator</span>
              <span className="hero-card-desc">Kiểm tra & đánh giá</span>
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
          <h2 className="section-title">Tính năng chính</h2>
          <p className="section-subtitle">
            Tất cả công cụ bạn cần để học tập hiệu quả, được hỗ trợ bởi AI tiên tiến nhất
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
            Chỉ cần 4 bước đơn giản để bắt đầu hành trình học tập thông minh
          </p>
        </div>
        <div className="steps-grid">
          <div className="step-card">
            <div className="step-number">1</div>
            <div className="step-icon">
              <Upload size={28} />
            </div>
            <h3>Import tài liệu</h3>
            <p>
              Tải lên tài liệu môn học (PDF, DOCX, PPTX). Hệ thống tự động xử lý
              và index nội dung.
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
            <h3>Lên kế hoạch</h3>
            <p>
              Study Planner tạo lộ trình học tập cá nhân hóa, đồng bộ với Google
              Calendar.
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
            <h3>Học & Hỏi đáp</h3>
            <p>
              Chatbot RAG giải đáp mọi thắc mắc dựa trên tài liệu, có trích dẫn
              nguồn.
            </p>
          </div>
          <div className="step-connector">
            <ArrowRight size={24} />
          </div>
          <div className="step-card">
            <div className="step-number">4</div>
            <div className="step-icon">
              <FileText size={28} />
            </div>
            <h3>Kiểm tra & Đánh giá</h3>
            <p>
              Tạo bài kiểm tra, đánh giá năng lực và LLM tự động điều chỉnh lộ
              trình.
            </p>
          </div>
        </div>
      </section>

      {/* Bottom CTA */}
      <section className="bottom-cta">
        <div className="cta-content">
          <div className="cta-decoration">
            <Zap size={40} />
          </div>
          <h2>Sẵn sàng nâng cao hiệu quả học tập?</h2>
          <p>
            Tham gia ngay để trải nghiệm hệ thống trợ lý học tập thông minh với
            AI tiên tiến nhất.
          </p>
          <div className="cta-features">
            <div className="cta-feature">
              <Shield size={18} />
              <span>Bảo mật dữ liệu</span>
            </div>
            <div className="cta-feature">
              <Zap size={18} />
              <span>Phản hồi tức thì</span>
            </div>
            <div className="cta-feature">
              <Mail size={18} />
              <span>Nhắc nhở qua Email</span>
            </div>
          </div>
          {user ? (
            <button
              className="hero-btn hero-btn-primary cta-btn"
              onClick={() => onNavigate("Dashboard")}
            >
              <BarChart3 size={20} />
              Vào Dashboard
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
            <GraduationCap size={24} />
            <span>Smart Learning Agent</span>
          </div>
          <p className="footer-text">
            © 2026 Smart Learning Agent — UET VNU. Built with AI for better learning.
          </p>
        </div>
      </footer>
    </div>
  );
};

export default Homepage;
