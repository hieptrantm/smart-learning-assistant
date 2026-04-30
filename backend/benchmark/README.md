# Benchmark Guide

Thư mục này chứa bộ benchmark để so sánh hai cách sinh learning path:

- `tree_based`: chạy trên cây `TreeRoot` / `TreeNode` được build từ Neo4j.
- `knowledge_graph`: chạy trực tiếp trên raw `Entity` graph trong Neo4j.

Benchmark được thiết kế để đo cả phần ingest lẫn phần planning, sau đó ghi report JSON để so sánh thời gian, token và context retention.

## 1. Các file chính

- `main.py`: entrypoint chạy benchmark. File này khởi tạo `TogetherLLM`, ingest dữ liệu nếu cần, sau đó chạy đồng thời `tree_based` và `knowledge_graph`.
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
- `tree_based.total_ms` và `knowledge_graph.total_ms`: thời gian chạy từng strategy.
- `total_prompt_tokens` và `avg_prompt_tokens`: lượng token prompt ước lượng.
- `context_retention_ratio`: tỉ lệ context edge giữ lại trong từng strategy.
- `payload_chunk_ratio`: tỉ lệ chunk thực sự được kéo vào payload học.
- `sessions[]`: chi tiết từng buổi học, gồm số node, số edge, số context node, token và preview nội dung.

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

## 5. Reset subject cũ

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

## 6. Chạy benchmark với `Cổ tích.pdf`

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

## 7. Chạy benchmark không ingest lại

Nếu subject đã được ingest sẵn và chỉ muốn benchmark planner:

```powershell
Set-Location "c:\Users\Home\OneDrive - vnu.edu.vn\Desktop\ComputerVisi\food-detector-agent\backend"
.\benchmark\.venv\Scripts\python.exe -m benchmark.main --subject-ids <subject_id> --skip-ingest
```

## 8. File output

Sau khi chạy xong, benchmark sẽ tạo:

- `output/subject_<subject_id>_benchmark.json`: report đầy đủ.
- `output/<subject_name>_knowledge_graph.json`: dump KG sau ingest.

Ví dụ:

- `output/subject_40_benchmark.json`
- `output/cổ tích_knowledge_graph.json`

## 9. Log cần chú ý

Các prefix log quan trọng:

- `[BenchmarkStrategyRunner]`: bắt đầu chạy từng strategy.
- `[TreeScheduler]`: log session của tree-based strategy.
- `[GraphScheduler]`: log session của knowledge-graph strategy.

Nếu thấy benchmark chậm, ưu tiên kiểm tra:

- thời gian tải embedding model `BAAI/bge-m3`.
- số request Together ở bước extraction / profiling.
- session rỗng có còn gọi LLM hay không.

## 10. Flow chuẩn để benchmark lại `Cổ tích.pdf`

1. Kích hoạt `.venv` của benchmark.
2. Chạy `reset_subject.py` với subject cũ của `cổ tích`.
3. Ghi lại `new_subject_id` mà script in ra.
4. Chạy `python -m benchmark.main --subject-ids <new_subject_id> --pdf-path ".\benchmark\Cổ tích.pdf"`.
5. Đọc `output/subject_<new_subject_id>_benchmark.json` để xem kết quả.