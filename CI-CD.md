# CI/CD cho ThinkCode OJ

Toan bo logic CI/CD nam trong GitHub Actions:

```text
.github/workflows/ci.yml
.github/workflows/cd.yml
```

Server khong giu `deploy.sh`, SSH wrapper, source code, private key, `.env`,
`local_settings.py` hoac file compose co dinh.

## Flow

`ci.yml` chay tren push va pull request:

**Không thể** làm blue-green deploy đúng nghĩa (chạy song song bản mới và bản cũ, test xong mới chuyển traffic) cho phần judge, vì:

- Judge worker thật (`thinkcode-judge-1`, container Docker riêng ngoài phạm vi CD này) chỉ duy trì **một kết nối TCP cố định** tới **một địa chỉ:port** ghi cứng trong `judge.yml` của nó (`localhost:9999`).
- DMOJ judge protocol không hỗ trợ "thử kết nối tới 2 bridge cùng lúc rồi chọn 1".
- Server chỉ có **1 judge worker** — không có worker thứ 2 để test độc lập.

Vì vậy quy trình thực tế là **cutover rồi verify ngay, tự động rollback nếu hỏng**:

1. `docker compose up -d` thay thế container `bridged` cũ bằng bản mới → có khoảng trống vài giây khi port 9999 được giải phóng và bind lại → judge worker phát hiện mất kết nối, tự động thử kết nối lại (đây là hành vi mặc định của DMOJ judge, không cần can thiệp gì thêm).
2. `deploy.sh` poll tối đa 90 giây, kiểm tra 2 điều kiện: site trả HTTP 200, và có ít nhất 1 row `Judge.online=True` trong DB. (Ban đầu để 60s, nhưng deploy thật đầu tiên cho thấy đôi khi không đủ -- `docker compose up -d` recreate cả 4 container cùng lúc vì chúng dùng chung 1 image, nên judge cần thêm ~10-20s để phát hiện mất kết nối và reconnect/xác thực lại; đã tăng lên 90s sau khi quan sát 2 lần deploy thật liên tiếp đều timeout ở ranh giới 60s dù judge trên thực tế vẫn reconnect thành công ngay sau đó.)
3. Nếu cả 2 đạt trong 90 giây → deploy thành công.
4. Nếu không → tự động `docker compose up -d` lại với **image cũ** (ghi lại trước đó trong `current_image.txt`), verify lại, rồi báo lỗi cho GitHub Actions (job fail) dù rollback có thành công hay không — để luôn có người biết và kiểm tra.

**Downtime thực tế ước tính**: vài giây tới ~10-15 giây cho phần chấm bài (bridged restart + judge reconnect), site có thể có 1-2 request lỗi trong lúc container `site` restart (uwsgi worker cần vài giây khởi động lại). Đây là đánh đổi hợp lý cho một single-judge-worker setup — nếu cần zero-downtime thật cho judge, xem mục 7 (hướng mở rộng).

**Health check hiện tại chỉ ở mức kết nối** (`Judge.online == True`), **không** chấm thử 1 bài test thật qua judge — theo lựa chọn đã thống nhất, ưu tiên tốc độ deploy hơn độ chắc chắn tuyệt đối. Nếu muốn nâng cấp lên chấm thử thật, xem mục 7.

---

## 3. Setup cần làm 1 lần (đã thực hiện, ghi lại để tham khảo/tái tạo)

### 3.1. Trên server

```bash
# Thêm user opencode vào group docker (để chạy docker/docker compose không cần sudo)
sudo usermod -aG docker opencode

# Thư mục deploy riêng, TÁCH BIỆT khỏi git checkout (source code giờ chỉ tồn
# tại bên trong Docker image, không cần checkout riêng trên server nữa)
mkdir -p /home/opencode/thinkcode-deploy
```

Khi CI tren branch `deploy` thanh cong, `cd.yml` se:

```text
checkout dung commit da test
build Docker image
push image len GHCR
SSH vao server
truyen GitHub Secrets qua stdin
docker login GHCR
pull image
check --deploy bang production env
migrate database
sync static assets
docker compose down
docker compose up -d
xoa config tam tren server
```

## GitHub Secrets

Tao GitHub Environment ten `production` va cac secrets:

### 3.3. Chuyển nginx sang trỏ TCP thay vì unix socket

**Chưa thực hiện tự động** — đây là bước cutover thủ công 1 lần, cần làm cẩn thận vì ảnh hưởng trực tiếp site đang chạy:

```bash
# Trên server, backup config cũ trước
sudo cp /etc/nginx/conf.d/vnoj.conf /etc/nginx/conf.d/vnoj.conf.native.bak

# Copy config mới (từ nginx/vnoj.conf.docker trong repo này) đè lên
sudo cp nginx/vnoj.conf.docker /etc/nginx/conf.d/vnoj.conf

# Tạo thư mục passthrough cho 502.html/robots.txt (deploy.sh sẽ tự sync file vào đây mỗi lần deploy)
sudo mkdir -p /var/www/thinkcodeoj/static-passthrough /var/www/thinkcodeoj/icons
sudo chmod 777 /var/www/thinkcodeoj/static-passthrough /var/www/thinkcodeoj/icons

# Test config trước khi reload
sudo nginx -t && sudo systemctl reload nginx
```

**Chỉ thực hiện bước này SAU KHI** đã chạy thành công deploy đầu tiên qua CD (để `/var/www/thinkcodeoj/static` đã có static assets mới từ image, tránh nginx trỏ vào file rỗng/thiếu).

---

## 3.4. Static assets + django-compressor: vì sao `/site/static` phải bind-mount, không chỉ copy-1-lần

Bug thật gặp phải ngày 15/08/2026: sau khi cutover, site load được nhưng **mất toàn bộ CSS** (404 trên mọi `/static/cache/css/output.<hash>.css`).

**Nguyên nhân**: `django-compressor` mặc định chạy ở chế độ **online** (`COMPRESS_OFFLINE` không set = `False`). Nghĩa là mỗi khi 1 trang có block `{% compress css %}` được render lần đầu trong 1 container, compressor tự tính hash (dựa trên mtime file nguồn) rồi **ghi file CSS đã minify vào `STATIC_ROOT/cache/css/` ngay lúc đó** -- không phải cố định sẵn từ lúc build image.

`deploy.sh` (bước 3) chỉ `docker cp` static assets ra host **một lần, trước cutover** -- coi `STATIC_ROOT` như dữ liệu tĩnh bất biến. Nhưng compressor online-mode không tĩnh: khi container `site` khởi động và xử lý request đầu tiên, nó tính ra một hash CSS khác (mtime các file trong image lệch theo thời điểm build), ghi vào bản `/site/static` **riêng của chính nó**. HTML trả về tham chiếu hash đó, nhưng file thật lại chỉ nằm trong container, không có trên host -- nginx (đọc thẳng từ đĩa) trả 404.

**Đã cân nhắc và loại bỏ**: bật `COMPRESS_OFFLINE = True` + chạy `manage.py compress` lúc build image (giống style cách CI hiện dùng để build CSS). Bị revert vì block `{% compress css %}` trong `templates/base.html` chọn CSS sáng/dark **tuỳ theo user** (`request.profile.site_theme` / cookie `site_theme`) -- nội dung block phụ thuộc request, không cố định, nên `manage.py compress` (chạy 1 lần, không có request thật) không đủ context để render đúng, hoặc phải enumerate thủ công mọi tổ hợp theme -- phức tạp và dễ vỡ khi thêm theme mới.

**Giải pháp đã áp dụng**: bind-mount thẳng `/var/www/thinkcodeoj/static` (thư mục host mà nginx `location /static` đọc trực tiếp) vào `/site/static` bên trong container `site` (xem `docker-compose.production.yml`). Đây chính là cách bản native cũ (site + nginx cùng máy, cùng ổ đĩa) và `thinkcode-docker` (named volume `assets:` mount chung cả site lẫn nginx container) vẫn luôn hoạt động đúng -- nguyên tắc chung: **compressor phải ghi runtime cache vào đúng chỗ mà web server đọc, không phải một bản sao riêng**. `deploy.sh` bước 3 (`docker cp` static ra host trước cutover) vẫn giữ nguyên -- nó vẫn cần thiết để đưa các asset KHÔNG qua compressor (JS lib, ảnh, icon, font, admin static) từ image mới ra host trước khi container mới lên; chỉ riêng phần compressor tự sinh (`cache/css/`, `cache/js/`) giờ không còn phụ thuộc bước copy đó nữa.

**Bug thứ hai gặp phải khi test fix trên** (cùng ngày): sau khi thêm bind-mount, request đầu tiên vẫn 500 với `PermissionError: [Errno 13] Permission denied: '/site/static/cache/css/output.<hash>.css'`. Nguyên nhân: `docker cp` (chạy dưới quyền root qua docker daemon) **không kế thừa permission `777` của thư mục cha** khi tạo thư mục con mới -- `cache/` và `cache/css/` từng được tạo thủ công lúc debug trước đó với quyền `755`, còn container `site` chạy dưới uid 1000 (`dmoj`, không phải root) nên không ghi được. Đã sửa bằng 2 việc:
1. `deploy.sh` bước 3 giờ chạy `chmod -R 777 "$STATIC_ROOT_HOST"` sau mỗi lần sync, để bất kỳ thư mục con mới nào (compressor tự tạo, hoặc app mới thêm static dir ở upstream) đều luôn world-writable, không phụ thuộc umask của `docker cp`.
2. Vì `deploy.sh` chạy dưới user `opencode` (không có NOPASSWD sudo, và cũng không nên có để giảm attack surface của deploy key), toàn bộ cây `/var/www/thinkcodeoj/static` phải **thuộc sở hữu `opencode`** để lệnh `chmod` ở bước 1 tự chạy được mà không cần `sudo`. Một số thư mục con còn sót lại quyền sở hữu `dmoj-uwsgi` (uid 998, từ thời native) đã được `sudo chown -R opencode:opencode /var/www/thinkcodeoj/static` một lần thủ công để dọn sạch -- **bước này cần lặp lại thủ công (1 lần) khi setup server mới** nếu thư mục `static/` được tạo trước đó bởi user/process khác `opencode` (ví dụ site native cũ đã từng chạy ở đó).

---

## 4. GitHub Actions secrets cần cấu hình

Vào repo `thinkcode-oj` trên GitHub → **Settings → Secrets and variables → Actions**, thêm:

| Secret | Giá trị |
|---|---|
| `DEPLOY_HOST` | IP hoac hostname production |
| `DEPLOY_USER` | User SSH co quyen chay Docker |
| `DEPLOY_SSH_KEY` | Private SSH key danh rieng cho CD |
| `PRODUCTION_ENV` | Toan bo noi dung file env production |

`GITHUB_TOKEN` duoc GitHub cap tu dong de push image va login GHCR.

`PRODUCTION_ENV` la multiline secret, vi du:

```dotenv
DJANGO_SECRET_KEY=...
DJANGO_DEBUG=False
ALLOWED_HOSTS=oj.thinkcode.vn
CSRF_TRUSTED_ORIGINS=https://oj.thinkcode.vn
DB_NAME=dmoj
DB_USER=dmoj
DB_PASSWORD=...
DB_HOST=127.0.0.1
DB_PORT=3306
REDIS_URL=redis://127.0.0.1:6379/0
CELERY_BROKER_URL=redis://127.0.0.1:6379/0
CELERY_RESULT_BACKEND=redis://127.0.0.1:6379/0
```

Khong dua secret production vao Dockerfile, source code hoac image layer.

## Production Image

`dmoj/local_settings.docker.py.example` khong chua secret va duoc copy vao
image voi ten `dmoj/local_settings.py` khi build.

File nay doc cau hinh tu environment runtime. CD truyen `PRODUCTION_ENV` vao
cac container bang `--env-file` hoac Compose.

## Server Setup

Server chi can:

- Docker Engine
- Docker Compose plugin
- User deploy thuoc group `docker`
- Public SSH key tuong ung voi `DEPLOY_SSH_KEY`
- Cac thu muc du lieu persistent:
  - `/var/www/thinkcodeoj/media`
  - `/var/www/thinkcodeoj/problem_data`
  - `/var/www/thinkcodeoj/static`
  - `/var/log/thinkcodeoj`

Public key trong `~/.ssh/authorized_keys` nen gioi han forwarding:

```text
no-port-forwarding,no-X11-forwarding,no-agent-forwarding,no-pty ssh-ed25519 AAAA... github-actions-cd
```

**Không còn phương án rollback native tức thời.** Trước 15/08/2026, `/home/opencode/vnojsite/` (source code + venv Python 3.8 native) và 4 file config supervisor (`bridged.conf`, `celery.conf`, `site.conf`, `wsevent.conf`) vẫn còn nguyên trên server, cho phép `sudo supervisorctl start site bridged celery wsevent` khôi phục ngay trong vài giây nếu Docker gặp sự cố không cứu được. Theo yêu cầu "server không giữ source code gì cả, chỉ pull image về chạy", toàn bộ đã bị xoá (config supervisor backup tại `/root/supervisor-native-backup/` trên server chỉ để tham khảo, KHÔNG dùng để chạy lại trực tiếp -- venv/node_modules đã mất).

Nếu Docker hoàn toàn không cứu được (lỗi hạ tầng nghiêm trọng, không phải lỗi image/code -- những trường hợp đó dùng rollback qua `deploy.sh`/`current_image.txt` ở trên), phương án duy nhất còn lại là cài native từ đầu bằng `vnoi_setup.sh`/`dmoj_judge_setup.sh` -- 2 script này **không nằm trong repo `thinkcode-oj`** (chưa từng được commit vào git nào), chỉ tồn tại local tại `/home/hlt/Documents/Projects/` trên máy phát triển; cần lấy lại từ đó trước khi chạy trên server. Toàn bộ quá trình mất khoảng 15-30 phút thay vì vài giây. `vnoj.conf.native.bak` (config nginx trỏ unix socket, không phải TCP) vẫn còn trên server tại `/etc/nginx/conf.d/`, có thể dùng lại sau khi site native được cài đặt lại.

## R2 Storage

R2 credentials are runtime-only. Do not put them in the Dockerfile, image,
repository, or a persistent server compose file. The application reads the
following variables from `PRODUCTION_ENV` when `USE_R2_MEDIA=True`:

```dotenv
USE_R2_MEDIA=False
R2_ACCESS_KEY_ID=...
R2_SECRET_ACCESS_KEY=...
R2_ENDPOINT_URL=https://<account-id>.r2.cloudflarestorage.com
R2_MEDIA_BUCKET=thinkcode-media
R2_MEDIA_CUSTOM_DOMAIN=media.oj.thinkcode.vn
R2_MEDIA_PRIVATE=False
R2_PROBLEMS_BUCKET=thinkcode-problems
```

MariaDB backups use a separate, backup-only R2 credential and the
`deploy/thinkcode-r2-backup.service` and `.timer` templates. The live database
remains on MariaDB; the backup job only runs `mariadb-dump --single-transaction`
and uploads a compressed copy.

Problem releases use `python manage.py publish_problem_release CODE VERSION`.
The site bridge sends `problem-version` and `problem-sha256` on each
submission. Judges with `r2_problems.enabled` download that package into
`/var/cache/dmoj-problems` and grade from the cache. R2 is never FUSE-mounted.

Set GitHub Actions variable `BRIDGED_R2_PROBLEMS=True` only after judges
understand the new packet fields. Until then, leave it false so missing
release metadata does not block dispatch. CD injects this into the
runtime env for `site`/`bridged`/`celery`.

Rollback for media is `USE_R2_MEDIA=False` followed by a normal CD deployment.
Rollback for judge R2 mode is `r2_problems.enabled: false` (or
`R2_PROBLEMS_ENABLED=False`) and remount the local `/problems` tree.

## Runtime Config Tam

Moi lan deploy, `cd.yml`:

1. Ma hoa noi dung `PRODUCTION_ENV` va `docker-compose.production.yml` bang base64 de truyen qua stdin.
2. Ghi chung vao `/tmp/thinkcode-deploy` tren server.
3. Chay validation, migration va Compose.
4. Xoa thu muc tam bang shell trap khi ket thuc.

Khong co file cau hinh deploy nao duoc giu lai sau workflow. Container van giu
environment runtime da duoc Docker nap khi khoi dong.

## Downtime Va Rollback

CD dung flow don gian:

```bash
docker compose down --remove-orphans
```

Vi vay co downtime ngan trong luc bon service `site`, `bridged`, `celery`,
`wsevent` duoc thay the. MariaDB, Redis va nginx native khong bi dung.

Phase nay chua co rollback tu dong. Image tag theo commit cho phep rollback
thu cong bang cach chay lai CD voi commit cu.
