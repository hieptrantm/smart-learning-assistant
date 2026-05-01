# Benchmark Guide

Thư mục này chứa bộ benchmark để so sánh hai cách sinh learning path:

- `tree_based`: chạy trên cây `TreeRoot` / `TreeNode` được build từ Neo4j.
- `knowledge_graph`: chạy trực tiếp trên raw `Entity` graph trong Neo4j.
- `vector_db_chunks`: chạy trực tiếp trên raw chunks đã index trong Qdrant, không dùng graph edges để lập plan.

Benchmark được thiết kế để đo cả phần ingest lẫn phần planning. Phần planning hiện tập trung vào 4 metric chính: thứ tự prerequisite, mức kích hoạt relation, độ lặp entity giữa các session và hiệu quả token.

## 1. Các file chính

- `main.py`: entrypoint chạy benchmark. File này khởi tạo `TogetherLLM`, ingest dữ liệu nếu cần, sau đó chạy đồng thời `tree_based`, `knowledge_graph` và `vector_db_chunks`.
- `ingestion_pipeline.py`: pipeline ingest dùng lại flow từ `data-ingestor`, gồm chunking, extraction, profiling, lưu Neo4j và Qdrant.
- `strategy_runner.py`: tải raw graph từ Neo4j, gọi tree scheduler và graph scheduler, rồi tổng hợp metrics.
- `reset_subject.py`: xóa một subject cũ khỏi Postgres, Neo4j, Qdrant và tạo lại subject mới với cùng metadata.
- `subject_repository.py`: đọc metadata subject và free slots từ DB.
- `models.py`: định nghĩa cấu trúc report benchmark.
- `llm/together_llm.py`: wrapper `TogetherLLM` dùng cho các bước sinh text trong benchmark.
- `llm_service.py`: adapter để `IndexingEngine` dùng `TogetherLLM` cho extraction, merge, profiling.
- `token_estimator.py`: ước lượng số token prompt cho từng strategy.
- `output/`: nơi ghi file benchmark report và KG JSON dump.
- `.env.example`: biến môi trường mẫu cho benchmark.
- `requirements.txt`: dependencies cần cho benchmark.

## 2. Benchmark đo gì

Report benchmark ghi các nhóm chỉ số sau:

- `ingestion.duration_ms`: thời gian ingest tổng.
- `ingestion.chunks`: số chunk đầu vào.
- `ingestion.entities_raw`: số entity extract thô.
- `ingestion.entities_profiled`: số entity sau profiling.
- `ingestion.relations`: số quan hệ extract được.
- `tree_based.total_ms`, `knowledge_graph.total_ms` và `vector_db_chunks.total_ms`: thời gian chạy từng strategy.
- `prerequisite_ordering_accuracy`: tỉ lệ prerequisite được sắp đúng thứ tự học.
- `relation_activation_rate`: tỉ lệ relation quan trọng (`PREREQUISITE`, `PART_OF`) thật sự được kích hoạt trong plan.
- `entity_redundancy_ratio`: mức lặp entity chính giữa các session.
- `tokens_per_unique_entity` và `avg_prompt_tokens`: hiệu quả token theo entity và theo session.
- `sessions[]`: chi tiết từng buổi học, gồm số primary entity, context entity, activated relation, token và preview nội dung.

Mô tả chi tiết cách tính và cách đọc các metric nằm trong file `METRICS.md`.

## 3. Yêu cầu môi trường

Cần có sẵn:

- PostgreSQL với database `authdb`.
- Neo4j chạy ở `bolt://localhost:7687`.
- Qdrant chạy ở `localhost:6333`.
- Together API key hợp lệ.
- Python 3.11.

Các biến môi trường benchmark nằm trong `.env` cùng thư mục này. Có thể tạo từ `.env.example`.

Ví dụ tối thiểu:

## 4. Cài môi trường benchmark

Chạy từ thư mục `backend/benchmark`:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## 5. Benchmark subject mới hoàn toàn

Nếu chưa có gì trong Postgres và chỉ muốn benchmark một subject mới từ PDF hoặc raw chunks, có thể truyền metadata trực tiếp qua CLI.

Chạy từ thư mục `backend`:

```bash
python -m benchmark.main \
  --subject-name "cổ tích" \
  --subject-id 50 \
  --slots fri=09:00-11:00 tue=13:00-15:00 \
  --pdf-path "benchmark/Cổ tích.pdf"
```

Ghi chú:

- `--subject-name` là khóa chính dùng để lưu KG vào Neo4j và Qdrant.
- `--subject-id` chỉ dùng để đặt tên report output. Nếu bỏ qua thì report sẽ dùng `subject_0_benchmark.json`.
- `--slots` là bắt buộc với subject mới. Có thể truyền slot dạng `day=09:00` hoặc `day=09:00-11:00`.
- Luồng này không đọc metadata từ Postgres.

## 6. Benchmark nhiều subject từ JSON

Nếu muốn chạy batch khoảng 10-20 môn học trong một lần, có thể dùng file manifest JSON. Benchmark sẽ khởi tạo runtime dùng chung trong một process để tránh warm-up lại dependency nặng cho từng môn.

Ví dụ file JSON:

```json
[
  {
    "subject_name": "cổ tíchhh",
    "subject_id": 100,
    "slot": "tue=14:00-16:00 fri=09:00-11:00",
    "pdf_path": "benchmark/data/Cổ tích.pdf"
  },
  {
    "subject_name": "lịch sử đảng",
    "subject_id": 101,
    "slot": "mon=08:00-10:00 wed=14:00-16:00",
    "pdf_path": "benchmark/data/lsd1.pdf"
  }
]
```

Các field bắt buộc:

- `subject_name`
- `subject_id`
- `pdf_path` hoặc `pdf_url`

Field tùy chọn:

- `slot` hoặc `slots`: chuỗi hoặc mảng slot dạng `day=09:00-11:00`
- `start_date`
- `target_grade`
- `end_date`
- `session_count`: ép số buổi học cố định
- `session_weight`: trọng số cho từng buổi khi dùng `session_count`
- `session_weights`: danh sách weight nếu muốn chỉ định từng buổi riêng lẻ

Chạy từ thư mục `backend`:

```bash
python -m benchmark.main \
  --subjects-json "benchmark/data/data_batch.json"
```

Nếu muốn xóa dữ liệu cũ của từng subject trước khi ingest lại:

```bash
python -m benchmark.main \
  --subjects-json "benchmark/data/data_batch.json" \
  --recreate
```

## 7. Reset subject cũ

Script `reset_subject.py` làm 3 việc:

- xóa subject cũ trong Postgres.
- xóa raw KG và tree graph trong Neo4j.
- xóa vector tương ứng trong các collection Qdrant.

Sau đó script tạo lại subject mới và in ra `new_subject_id`.

Mẫu lệnh:

```powershell
Set-Location "c:\Users\Home\OneDrive - vnu.edu.vn\Desktop\ComputerVisi\food-detector-agent\backend\benchmark"
.\.venv\Scripts\python.exe .\reset_subject.py \
  --subject-id <old_subject_id> \
  --name "cổ tích" \
  --user-id 1 \
  --target-grade 7.0 \
  --end-date 2026-05-02 \
  --slots fri=09:00 fri=10:00 fri=11:00 fri=12:00 tue=11:00 tue=12:00 tue=13:00
```

Ví dụ output:

```text
{'new_subject_id': 40, 'subject_name': 'cổ tích'}
```

Lấy `new_subject_id` này để chạy benchmark tiếp theo.

## 8. Xóa sạch toàn bộ subject data

Nếu không nhớ trong Postgres, Neo4j và Qdrant đang có những môn nào, có thể xóa sạch toàn bộ subject data bằng script sau.

Script sẽ:

- xóa toàn bộ `study_subjects` trong Postgres và để cascade các bảng phụ như `subject_free_slots`, `subject_documents`, `study_plans`, `study_sessions`, `subject_messages`
- xóa toàn bộ node Neo4j có `subject_id`
- drop và recreate các collection Qdrant dùng cho ingest: `raw_chunks`, `low-level-retrieval`, `high-level-retrieval`

Chạy từ thư mục `backend`:

```bash
python -m benchmark.reset_all_subjects --yes
```

Script yêu cầu `--yes` để tránh xóa nhầm.

## 9. Chạy benchmark với `Cổ tích.pdf`

Chạy từ thư mục `backend` để import package `benchmark` đúng cách:

```powershell
Set-Location "c:\Users\Home\OneDrive - vnu.edu.vn\Desktop\ComputerVisi\food-detector-agent\backend"
.\benchmark\.venv\Scripts\python.exe -m benchmark.main --subject-ids <new_subject_id> --pdf-path ".\benchmark\Cổ tích.pdf"
```

Ví dụ với subject mới là `40`:

```powershell
Set-Location "c:\Users\Home\OneDrive - vnu.edu.vn\Desktop\ComputerVisi\food-detector-agent\backend"
.\benchmark\.venv\Scripts\python.exe -m benchmark.main --subject-ids 40 --pdf-path ".\benchmark\Cổ tích.pdf"
```

## 10. Chạy benchmark không ingest lại

Nếu subject đã được ingest sẵn và chỉ muốn benchmark planner:

```powershell
Set-Location "c:\Users\Home\OneDrive - vnu.edu.vn\Desktop\ComputerVisi\food-detector-agent\backend"
.\benchmark\.venv\Scripts\python.exe -m benchmark.main --subject-ids <subject_id> --skip-ingest
```

## 11. File output

Sau khi chạy xong, benchmark sẽ tạo:

- `output/subject_<subject_id>_benchmark.json`: report đầy đủ.
- `output/<subject_name>_knowledge_graph.json`: dump KG sau ingest.

Ví dụ:

- `output/subject_40_benchmark.json`
- `output/cổ tích_knowledge_graph.json`

## 12. Log cần chú ý

Các prefix log quan trọng:

- `[BenchmarkStrategyRunner]`: bắt đầu chạy từng strategy.
- `[TreeScheduler]`: log session của tree-based strategy.
- `[GraphScheduler]`: log session của knowledge-graph strategy.

Nếu thấy benchmark chậm, ưu tiên kiểm tra:

- thời gian tải embedding model `BAAI/bge-m3`.
- số request Together ở bước extraction / profiling.
- session rỗng có còn gọi LLM hay không.

## 13. Flow chuẩn để benchmark lại `Cổ tích.pdf`

1. Kích hoạt `.venv` của benchmark.
2. Chạy `reset_subject.py` với subject cũ của `cổ tích`.
3. Ghi lại `new_subject_id` mà script in ra.
4. Chạy `python -m benchmark.main --subject-ids <new_subject_id> --pdf-path ".\benchmark\Cổ tích.pdf"`.
5. Đọc `output/subject_<new_subject_id>_benchmark.json` để xem kết quả.