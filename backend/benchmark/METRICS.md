# Các Chỉ Số Đánh Giá Kế Hoạch Học

Bộ benchmark này tập trung vào 4 chỉ số chính cho bài toán xây dựng learning path. Mục tiêu là so sánh cách từng chiến lược tổ chức tri thức qua các buổi học, không chỉ kiểm tra việc tri thức có tồn tại trong graph hay không.

Các chiến lược hiện tại:

- tree_based: lập kế hoạch từ biểu diễn cây được suy ra từ knowledge graph
- knowledge_graph: lập kế hoạch trực tiếp từ graph thực thể thô
- vector_db_chunks: lập kế hoạch trực tiếp từ raw chunks trong Qdrant, không suy luận theo cạnh của graph

## 1. prerequisite_ordering_accuracy

Đo mức độ sắp xếp đúng thứ tự tiên quyết giữa các khái niệm.

- Ground truth: toàn bộ quan hệ PREREQUISITE trong graph thô của môn học.
- Gán buổi học: với mỗi thực thể, lấy buổi đầu tiên mà thực thể đó xuất hiện như một primary learning node.
- Một quan hệ tiên quyết A -> B được xem là đúng khi session(A) <= session(B).

Công thức:

$$
prerequisite\_ordering\_accuracy = \frac{\#correct\_prerequisite\_relations}{\#evaluable\_prerequisite\_relations}
$$

Các bộ đếm hỗ trợ trong báo cáo:

- prerequisite_total
- prerequisite_evaluable
- prerequisite_correct
- prerequisite_violations

Cách đọc chỉ số:

- Càng cao càng tốt.
- Điểm thấp cho thấy planner đang đưa nội dung nâng cao lên trước nền tảng cần học trước.

## 2. relation_activation_rate

Đo mức độ các quan hệ quan trọng trong graph có thực sự được thể hiện trong các buổi học đã sinh hay không.

- Ground truth: toàn bộ các quan hệ quan trọng trong graph thô.
- Loại quan hệ quan trọng hiện tại:
  - PREREQUISITE
  - PART_OF
- Một quan hệ được tính là activated khi nó xuất hiện trong runtime relations của buổi học hoặc được giữ lại qua tags của tree node.

Công thức:

$$
relation\_activation\_rate = \frac{\#activated\_key\_relations}{\#all\_key\_relations}
$$

Báo cáo cũng tách riêng:

- prerequisite_activation_rate
- part_of_activation_rate

Cách đọc chỉ số:

- Càng cao càng tốt.
- Điểm cao cho thấy planner không chỉ phủ thực thể, mà còn giữ được cấu trúc và phụ thuộc giữa chúng.

## 3. entity_redundancy_ratio

Đo mức độ lặp lại cùng một primary entity giữa các buổi học.

- Chỉ dùng primary learning nodes cho chỉ số này.
- Không tính context nodes vì lặp lại ở context có thể là hợp lý và hữu ích.

Công thức:

$$
entity\_redundancy\_ratio = \frac{\sum_i |P_i| - |\bigcup_i P_i|}{\sum_i |P_i|}
$$

Trong đó:

- P_i là tập primary entities ở buổi học i

Các trường hỗ trợ:

- unique_primary_entities
- total_primary_entity_mentions
- avg_adjacent_entity_overlap

Cách đọc chỉ số:

- Nhìn chung càng thấp càng tốt.
- Redundancy quá cao nghĩa là nhiều buổi đang dạy lại cùng nội dung chính.
- Redundancy quá thấp cũng có thể là dấu hiệu kế hoạch bị rời rạc, nên cần đọc kèm avg_adjacent_entity_overlap để cân bằng diễn giải.

## 4. tokens_per_unique_entity

Đo hiệu quả token: cần bao nhiêu prompt tokens để tổ chức mỗi unique primary entity.

Công thức:

$$
tokens\_per\_unique\_entity = \frac{total\_prompt\_tokens}{\#unique\_primary\_entities}
$$

Trường hỗ trợ:

- avg_prompt_tokens, tương đương số tokens trung bình cho mỗi buổi

Cách đọc chỉ số:

- Càng thấp càng tốt.
- Điểm thấp cho thấy planner tổ chức được nhiều tri thức duy nhất hơn trên mỗi token chi phí.

## Các Trường Ở Mức Buổi Học

Mỗi buổi học lưu một số thống kê nhẹ để giải thích kết quả ở mức chiến lược:

- primary_entity_count
- context_entity_count
- activated_relation_count
- activated_prerequisite_count
- activated_part_of_count
- prompt_tokens
- aggregate_preview

## Thứ Tự Ưu Tiên Khi Diễn Giải

Khi đánh giá chất lượng kế hoạch học, nên đọc theo thứ tự:

1. prerequisite_ordering_accuracy
2. relation_activation_rate
3. entity_redundancy_ratio
4. tokens_per_unique_entity

Trong thực tế, một planner tốt nên:

- giữ thứ tự tiên quyết ở mức cao,
- kích hoạt được phần lớn các quan hệ quan trọng,
- tránh lặp lại thực thể quá mức,
- đồng thời duy trì chi phí token ở mức hợp lý.