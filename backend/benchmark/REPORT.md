# Giải Thích Các Tỷ Lệ Và Chỉ Số Trong Benchmark

Tài liệu này giải thích chi tiết các tỷ lệ và chỉ số chính đang xuất hiện trong báo cáo benchmark giữa hai chiến lược `tree_based` và `vector_db_chunks`.

Mỗi mục được trình bày theo cùng một cấu trúc:

- tên gốc bằng tiếng Anh;
- công thức tính;
- ý nghĩa của từng thành phần trong công thức;
- cách diễn giải khi tỷ lệ cao hoặc thấp.

## 0. Ý Tưởng Của Hai Giải Pháp Được So Sánh

Trước khi đọc các tỷ lệ, cần hiểu rằng benchmark này không chỉ so sánh hai kết quả đầu ra khác nhau, mà đang so sánh hai cách tổ chức tri thức khác nhau.

### 0.1. Tree-based

Tên gốc bằng tiếng Anh: `tree_based`

#### Ý tưởng cốt lõi

Giải pháp `tree_based` xuất phát từ giả định rằng tri thức nên được tổ chức theo một cấu trúc gần giống cây học tập.

Thay vì chỉ lấy ra các đoạn nội dung liên quan, cách làm này cố gắng:

- dựng lại một cấu trúc phân cấp từ knowledge graph;
- gom các thực thể thành các cụm có quan hệ cha-con hoặc quan hệ phụ thuộc;
- chọn nội dung học theo hướng từ khái niệm nền tảng đến khái niệm mở rộng.

Nói ngắn gọn, `tree_based` muốn trả lời câu hỏi:

"Nếu xem môn học như một cấu trúc có thứ bậc, thì nên học nhánh nào trước, nhánh nào sau?"

#### Cách hoạt động ở mức ý tưởng

- Bắt đầu từ graph tri thức đã ingest.
- Suy ra hoặc tái cấu trúc graph thành dạng cây hay gần-cây.
- Chọn các node trung tâm làm khung cho từng buổi học.
- Giữ lại quan hệ tiên quyết và quan hệ thành phần để đảm bảo lộ trình học có thứ tự.

#### Điểm mạnh

- Phù hợp khi mục tiêu là giữ cấu trúc học rõ ràng.
- Thường có lợi thế ở các chỉ số liên quan đến logic sư phạm như thứ tự tiên quyết.
- Dễ tạo cảm giác chương trình học có mạch và có khung.

#### Điểm yếu

- Thường tốn nhiều token hơn vì phải mang theo nhiều context cấu trúc.
- Có thể chậm hơn do planner phải xử lý thêm lớp tổ chức tri thức.
- Nếu cây suy ra từ graph chưa tốt, planner có thể bị cứng hoặc bỏ sót một số liên kết hữu ích ngoài cấu trúc cây.

### 0.2. Vector DB Chunks

Tên gốc bằng tiếng Anh: `vector_db_chunks`

#### Ý tưởng cốt lõi

Giải pháp `vector_db_chunks` xuất phát từ giả định rằng có thể xây dựng kế hoạch học bằng cách truy hồi trực tiếp các đoạn nội dung tốt nhất từ vector database, thay vì bắt buộc phải đi qua một cấu trúc cây hay graph đã chuẩn hóa.

Thay vì tổ chức tri thức theo khung phân cấp trước, cách này ưu tiên:

- lấy các chunk nội dung gần nhất với nhu cầu của session;
- gom các chunk liên quan lại với nhau;
- để nội dung retrieval quyết định phần lớn phạm vi kiến thức được đưa vào buổi học.

Nói ngắn gọn, `vector_db_chunks` muốn trả lời câu hỏi:

"Nếu lấy trực tiếp những đoạn nội dung phù hợp nhất, liệu có thể tạo ra buổi học tốt mà không cần ràng buộc mạnh bởi cấu trúc cây hay không?"

#### Cách hoạt động ở mức ý tưởng

- Bắt đầu từ các raw chunks đã được index trong vector database.
- Truy hồi các chunk gần nhất với nhu cầu planning của từng buổi.
- Tổng hợp nội dung từ các chunk này thành session output.
- Giữ quan hệ tri thức ở mức gián tiếp thông qua nội dung chunk, thay vì ép planner phải đi theo một khung cấu trúc cố định.

#### Điểm mạnh

- Thường nhanh hơn và rẻ hơn về token.
- Có khả năng phủ nội dung rộng vì retrieval trực tiếp từ chunk thường linh hoạt.
- Phù hợp khi ưu tiên throughput hoặc chi phí vận hành.

#### Điểm yếu

- Dễ mất cấu trúc học nếu retrieval không đủ kỷ luật.
- Có thể kích hoạt được nhiều nội dung nhưng không chắc giữ đúng thứ tự học.
- Dễ tạo kế hoạch học “hợp lý cục bộ” nhưng kém mạch lạc khi nhìn toàn bộ môn học.

### 0.3. Tóm Tắt Khác Biệt Cốt Lõi

Hai giải pháp khác nhau ở điểm trung tâm sau:

- `tree_based` ưu tiên tổ chức tri thức trước, rồi mới sinh kế hoạch học.
- `vector_db_chunks` ưu tiên truy hồi nội dung trước, rồi mới tổng hợp thành kế hoạch học.

Vì vậy, khi đọc benchmark:

- nếu `tree_based` tốt hơn ở `prerequisite_ordering_accuracy`, điều đó phù hợp với bản chất của hướng tiếp cận này;
- nếu `vector_db_chunks` tốt hơn ở `tokens_per_unique_entity`, điều đó cũng phù hợp với bản chất retrieval trực tiếp của nó;
- nếu một giải pháp thắng ở mọi chỉ số thì đó mới là tín hiệu mạnh, còn trong đa số trường hợp hai bên sẽ tạo ra trade-off khác nhau.

## 1. Prerequisite Ordering Accuracy

Tên gốc bằng tiếng Anh: `prerequisite_ordering_accuracy`

### Khái niệm

Chỉ số này đo mức độ planner sắp xếp đúng thứ tự học giữa các khái niệm có quan hệ tiên quyết.

Nếu một quan hệ tiên quyết có dạng $A \rightarrow B$, thì về mặt học thuật cần hiểu là người học nên học $A$ trước hoặc cùng buổi với $B$, chứ không nên học $B$ trước khi có nền tảng từ $A$.

### Công thức

$$
prerequisite\_ordering\_accuracy = \frac{\#correct\_prerequisite\_relations}{\#evaluable\_prerequisite\_relations}
$$

### Giải thích các thành phần

- `correct_prerequisite_relations`: số cặp kiến thức mà planner đã xếp đúng thứ tự học trước - học sau.
- `evaluable_prerequisite_relations`: số cặp kiến thức mà benchmark thật sự kiểm tra được thứ tự.

Có thể hiểu đơn giản như sau:

- nếu một khái niệm phải học trước một khái niệm khác, thì benchmark sẽ kiểm tra planner có làm đúng điều đó hay không;
- `correct_prerequisite_relations` là số lần planner làm đúng;
- `evaluable_prerequisite_relations` là tổng số lần benchmark có đủ thông tin để chấm đúng/sai.

Vì thế, tỷ lệ này thực chất là:

- lấy số quan hệ tiên quyết được xếp đúng;
- chia cho tổng số quan hệ tiên quyết có thể kiểm tra.

Một quan hệ tiên quyết được xem là đúng khi:

$$
session(A) \le session(B)
$$

Trong đó:

- `session(A)` là buổi đầu tiên mà khái niệm $A$ xuất hiện như nội dung học chính.
- `session(B)` là buổi đầu tiên mà khái niệm $B$ xuất hiện như nội dung học chính.

Diễn giải dễ hiểu hơn:

- nếu $A$ là kiến thức nền và $B$ là kiến thức nâng cao, thì phải học $A$ trước hoặc ít nhất là cùng buổi với $B`;
- nếu planner lại cho $B$ xuất hiện trước $A$, thì quan hệ đó bị tính là sai.

Ví dụ:

- giả sử `Biến` phải học trước `Hàm số`;
- nếu `Biến` xuất hiện lần đầu ở buổi 2 và `Hàm số` xuất hiện lần đầu ở buổi 4, thì đây là đúng vì $2 \le 4$;
- nếu `Hàm số` lại xuất hiện ở buổi 1 còn `Biến` ở buổi 3, thì đây là sai vì người học bị đưa vào phần nâng cao trước khi có nền tảng.

### Các trường hỗ trợ liên quan

- `prerequisite_total`: tổng số quan hệ tiên quyết trong graph gốc.
- `prerequisite_evaluable`: số quan hệ tiên quyết có thể đem ra đánh giá.
- `prerequisite_correct`: số quan hệ tiên quyết được sắp đúng.
- `prerequisite_violations`: số quan hệ tiên quyết bị vi phạm thứ tự.

### `total` và `evaluable` khác nhau ở đâu?

Đây là chỗ dễ nhầm nhất khi đọc báo cáo.

- `total` nghĩa là tổng số quan hệ có trong dữ liệu gốc.
- `evaluable` nghĩa là số quan hệ trong `total` mà benchmark thật sự chấm được đúng hay sai.

Nói đơn giản:

- `total` là "có bao nhiêu quan hệ tồn tại trong graph";
- `evaluable` là "trong số đó, có bao nhiêu quan hệ đủ thông tin để đem ra kiểm tra thứ tự học".

Vì vậy, luôn có khả năng:

$$
evaluable \le total
$$

### Vì sao có quan hệ nằm trong `total` nhưng không nằm trong `evaluable`?

Một quan hệ tiên quyết chỉ được tính là `evaluable` khi benchmark tìm được buổi xuất hiện đầu tiên của cả hai đầu mút trong quan hệ đó.

Ví dụ, với quan hệ:

$$
A \rightarrow B
$$

thì benchmark cần biết:

- $A$ xuất hiện lần đầu ở buổi nào;
- $B$ xuất hiện lần đầu ở buổi nào.

Nếu thiếu một trong hai thông tin này, benchmark không thể kết luận quan hệ đó đúng hay sai, nên quan hệ đó:

- vẫn nằm trong `prerequisite_total`;
- nhưng không được tính vào `prerequisite_evaluable`.

### Ví dụ dễ hiểu

Giả sử trong graph gốc có 5 quan hệ tiên quyết:

1. `Biến -> Hàm số`
2. `Hàm số -> Đạo hàm`
3. `Đạo hàm -> Tích phân`
4. `Giới hạn -> Đạo hàm`
5. `Ma trận -> Định thức`

Như vậy:

- `prerequisite_total = 5`

Nhưng khi sinh kế hoạch học, benchmark chỉ tìm thấy buổi xuất hiện đầu tiên của các khái niệm trong 4 quan hệ đầu. Riêng quan hệ `Ma trận -> Định thức` không chấm được vì `Định thức` chưa từng xuất hiện như `primary learning node` trong kế hoạch.

Khi đó:

- `prerequisite_total = 5`
- `prerequisite_evaluable = 4`

Giả sử trong 4 quan hệ chấm được đó:

- 3 quan hệ được xếp đúng thứ tự;
- 1 quan hệ bị xếp sai.

Khi đó:

- `prerequisite_correct = 3`
- `prerequisite_violations = 1`

và chỉ số sẽ là:

$$
prerequisite\_ordering\_accuracy = \frac{3}{4} = 0.75
$$

Lưu ý quan trọng:

- benchmark chia cho `evaluable`, không chia cho `total`;
- vì chỉ những quan hệ thật sự chấm được mới nên đi vào mẫu số.

### Ý nghĩa của tỷ lệ

- Tỷ lệ càng cao càng tốt.
- Nếu tỷ lệ gần `1.0`, planner đang giữ được logic học từ nền tảng đến nâng cao khá tốt.
- Nếu tỷ lệ thấp, planner có xu hướng đưa kiến thức nâng cao lên quá sớm, khiến lộ trình học kém tự nhiên và khó tiếp thu.

### Cách hiểu thực tế

- Đây là chỉ số quan trọng nhất nếu mục tiêu là chất lượng sư phạm.
- Một planner nhanh nhưng `prerequisite_ordering_accuracy` thấp vẫn có thể là planner kém về mặt dạy học.

## 2. Relation Activation Rate

Tên gốc bằng tiếng Anh: `relation_activation_rate`

### Khái niệm

Chỉ số này đo mức độ các quan hệ quan trọng trong graph gốc có thực sự được kích hoạt và phản ánh trong các buổi học sinh ra hay không.

Ở benchmark hiện tại, các quan hệ quan trọng chủ yếu gồm:

- `PREREQUISITE`
- `PART_OF`

### Công thức

$$
relation\_activation\_rate = \frac{\#activated\_key\_relations}{\#all\_key\_relations}
$$

### Giải thích các thành phần

- `activated_key_relations`: số quan hệ quan trọng thực sự xuất hiện trong runtime planning.
- `all_key_relations`: tổng số quan hệ quan trọng trong graph gốc của môn học.

Một quan hệ được xem là `activated` khi nó được giữ lại trong quá trình planner xây dựng buổi học, ví dụ:

- xuất hiện trong runtime relations của session;
- hoặc được bảo toàn thông qua tags hay cấu trúc node trong planner.

### Các trường hỗ trợ liên quan

- `key_relation_total`: tổng số quan hệ quan trọng.
- `activated_relation_total`: số quan hệ quan trọng đã được kích hoạt.
- `prerequisite_activation_rate`: tỷ lệ kích hoạt riêng cho quan hệ `PREREQUISITE`.
- `part_of_activation_rate`: tỷ lệ kích hoạt riêng cho quan hệ `PART_OF`.

### Ý nghĩa của tỷ lệ

- Tỷ lệ càng cao càng tốt.
- Nếu tỷ lệ gần `1.0`, planner không chỉ phủ được thực thể mà còn bảo toàn được cấu trúc liên hệ giữa các thực thể.
- Nếu tỷ lệ thấp, planner có thể đang chọn đúng một số nội dung nhưng đánh mất mối liên kết giữa chúng.

### Cách hiểu thực tế

- Chỉ số này trả lời câu hỏi: planner có “giữ được khung tri thức” hay không.
- Hai planner có thể dạy cùng một tập khái niệm, nhưng planner có `relation_activation_rate` cao hơn sẽ giữ được cấu trúc môn học tốt hơn.

## 3. Prerequisite Activation Rate

Tên gốc bằng tiếng Anh: `prerequisite_activation_rate`

### Khái niệm

Đây là một phiên bản chuyên biệt của `relation_activation_rate`, chỉ đo riêng mức độ các quan hệ `PREREQUISITE` được kích hoạt.

### Công thức

$$
prerequisite\_activation\_rate = \frac{\#activated\_prerequisite\_relations}{\#all\_prerequisite\_relations}
$$

### Ý nghĩa của tỷ lệ

- Tỷ lệ càng cao càng tốt.
- Nếu tỷ lệ cao, planner đang đưa được nhiều quan hệ nền tảng-phụ thuộc vào lộ trình học.
- Nếu tỷ lệ thấp, planner có thể vẫn tạo ra bài học hợp lý cục bộ nhưng thiếu liên kết tiên quyết trên phạm vi toàn môn.

### Cách hiểu thực tế

- Chỉ số này bổ sung cho `prerequisite_ordering_accuracy`.
- Một planner có thể sắp đúng thứ tự trên số ít quan hệ được dùng, nhưng nếu `prerequisite_activation_rate` thấp thì nghĩa là nhiều quan hệ tiên quyết vẫn chưa được tận dụng.

## 4. Part-of Activation Rate

Tên gốc bằng tiếng Anh: `part_of_activation_rate`

### Khái niệm

Chỉ số này đo mức độ các quan hệ `PART_OF` được giữ lại trong kế hoạch học.

Quan hệ `PART_OF` thường biểu diễn cấu trúc thành phần, ví dụ:

- một ý nhỏ thuộc về một chương lớn;
- một khái niệm con thuộc về một khái niệm bao quát hơn.

### Công thức

$$
part\_of\_activation\_rate = \frac{\#activated\_part\_of\_relations}{\#all\_part\_of\_relations}
$$

### Ý nghĩa của tỷ lệ

- Tỷ lệ càng cao càng tốt.
- Nếu tỷ lệ cao, planner giữ được cấu trúc phân cấp của nội dung học.
- Nếu tỷ lệ thấp, các buổi học có thể trở nên rời rạc, thiếu cảm giác “đang học trong cùng một khung chương mục”.

### Cách hiểu thực tế

- Chỉ số này quan trọng khi muốn đánh giá tính mạch lạc của toàn bộ chương trình học.
- Nó đặc biệt hữu ích khi so sánh planner dựa trên graph với planner dựa trên retrieval đơn thuần.

## 5. Entity Redundancy Ratio

Tên gốc bằng tiếng Anh: `entity_redundancy_ratio`

### Khái niệm

Chỉ số này đo mức độ lặp lại của cùng một `primary entity` giữa các buổi học.

Ở đây chỉ tính `primary learning nodes`, không tính `context nodes`, vì việc lặp context đôi khi là cần thiết để tạo tính liên kết giữa các buổi.

### Công thức

$$
entity\_redundancy\_ratio = \frac{\sum_i |P_i| - |\bigcup_i P_i|}{\sum_i |P_i|}
$$

Trong đó:

- $P_i$ là tập `primary entities` ở buổi học thứ $i$.
- $\sum_i |P_i|$ là tổng số lượt xuất hiện của các primary entities qua tất cả các buổi.
- $|\bigcup_i P_i|$ là số primary entities duy nhất trên toàn bộ kế hoạch học.

### Giải thích trực giác

- Nếu một entity xuất hiện lặp đi lặp lại như nội dung chính ở nhiều buổi, tử số sẽ tăng.
- Nếu phần lớn entity chỉ xuất hiện một lần như nội dung chính, tử số sẽ nhỏ.

### Các trường hỗ trợ liên quan

- `unique_primary_entities`: số primary entities duy nhất.
- `total_primary_entity_mentions`: tổng số lượt primary entities được nhắc đến.
- `avg_adjacent_entity_overlap`: độ chồng lấp entity trung bình giữa các buổi liền kề.

### Ý nghĩa của tỷ lệ

- Nhìn chung tỷ lệ càng thấp càng tốt.
- Tỷ lệ cao nghĩa là planner đang dạy lại cùng nội dung chính quá nhiều lần.
- Tỷ lệ thấp nghĩa là planner phân phối nội dung chính gọn và ít lặp hơn.

### Lưu ý khi diễn giải

- Không nên nhìn chỉ số này một mình.
- Nếu `entity_redundancy_ratio` quá thấp nhưng `avg_adjacent_entity_overlap` cũng gần `0`, kế hoạch học có thể bị rời rạc quá mức.
- Vì vậy, redundancy thấp là tốt, nhưng vẫn cần có một mức liên kết hợp lý giữa các buổi.

## 6. Tokens Per Unique Entity

Tên gốc bằng tiếng Anh: `tokens_per_unique_entity`

### Khái niệm

Đây không phải là một “tỷ lệ chất lượng học” theo nghĩa cấu trúc tri thức, mà là một chỉ số hiệu quả chi phí token.

Nó cho biết trung bình cần bao nhiêu prompt token để planner tổ chức được một `unique primary entity`.

### Công thức

$$
tokens\_per\_unique\_entity = \frac{total\_prompt\_tokens}{\#unique\_primary\_entities}
$$

### Giải thích các thành phần

- `total_prompt_tokens`: tổng số token prompt đã dùng trong toàn bộ planning.
- `unique_primary_entities`: số primary entities duy nhất thực sự được planner tổ chức thành nội dung học.

### Trường hỗ trợ liên quan

- `avg_prompt_tokens`: số token trung bình cho mỗi buổi học.

### Ý nghĩa của chỉ số

- Giá trị càng thấp càng tốt.
- Nếu chỉ số thấp, planner đang khai thác token hiệu quả hơn.
- Nếu chỉ số cao, planner phải tốn nhiều token hơn để tổ chức mỗi đơn vị tri thức duy nhất.

### Cách hiểu thực tế

- Đây là chỉ số quan trọng nếu quan tâm đến chi phí vận hành LLM.
- Tuy nhiên, một planner có `tokens_per_unique_entity` thấp không tự động tốt hơn về mặt sư phạm; nó chỉ tốt hơn về hiệu suất chi phí.

## 7. Thứ Tự Ưu Tiên Khi Đọc Báo Cáo

Khi đọc benchmark, nên ưu tiên các chỉ số theo thứ tự sau:

1. `prerequisite_ordering_accuracy`
2. `relation_activation_rate`
3. `entity_redundancy_ratio`
4. `tokens_per_unique_entity`

Lý do là:

- thứ tự tiên quyết phản ánh trực tiếp chất lượng sư phạm;
- kích hoạt quan hệ phản ánh việc giữ được cấu trúc tri thức;
- độ lặp phản ánh mức phân phối nội dung giữa các buổi;
- chi phí token phản ánh hiệu suất vận hành, không phải chất lượng học thuần túy.

## 8. Tóm Tắt Diễn Giải Nhanh

- `prerequisite_ordering_accuracy` cao: học đúng nền tảng trước, nâng cao sau.
- `relation_activation_rate` cao: planner giữ được quan hệ tri thức trong graph.
- `prerequisite_activation_rate` cao: tận dụng tốt các quan hệ tiên quyết.
- `part_of_activation_rate` cao: giữ được cấu trúc thành phần và phân cấp nội dung.
- `entity_redundancy_ratio` thấp: ít lặp lại cùng nội dung chính ở nhiều buổi.
- `tokens_per_unique_entity` thấp: hiệu quả token tốt hơn.

## 9. Kết Luận

Một planner tốt không nên chỉ nhanh hoặc chỉ rẻ về token. Về lý tưởng, nó cần đồng thời:

- giữ đúng thứ tự tiên quyết;
- giữ được nhiều quan hệ quan trọng trong graph;
- tránh lặp lại nội dung chính không cần thiết;
- và duy trì chi phí token ở mức hợp lý.

Vì vậy, khi so sánh `tree_based` với `vector_db_chunks`, cần đọc các tỷ lệ này như một bộ chỉ số phối hợp, thay vì chỉ nhìn một metric đơn lẻ.