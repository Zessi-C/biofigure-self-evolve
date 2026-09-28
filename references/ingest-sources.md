# 从各类材料中获取 figure 图像

本流程为模式 A 的第一步，其核心目的均在于获取可供精细判读的高质量图像文件（PNG/JPG）。文中所列命令均已于本机验证其实际可用性；若遇执行环境依赖缺失，应依各部分备选方案实施降级处理。

获取图像文件后，一律先行调用 Read 检视全貌；对于注记微小或尺寸受限的局部面板，须先将其裁剪放大为局部视图再行辨识，待细节核验无误后方可推进至解剖步骤。

## 1. 本地图片 / 截图

直接通过 Read 载入目标文件即可，无需进行格式转换。若输入为包含多个面板的整版截图，宜先通览原始版面，解剖阶段再逐一细分核对；若需将单块面板另存为独立条目的 reference，可借助 PIL 执行裁切：

```bash
python3 -c "
from PIL import Image
im = Image.open('输入.png')
im.crop((left, top, right, bottom)).save('面板.png')  # 像素坐标按显示比例换算
"
```

## 2. PDF（论文、补充材料）

先使用 pdftoppm 将目标页面栅格化为 PNG（分辨率以 200dpi 起步，以确保细小文字与注释清晰可读），随后调用 PIL 裁切出独立的 figure 区域：

```bash
pdftoppm -png -r 200 -f 5 -l 5 paper.pdf page    # 第5页 → page-5.png
```

- 若 figure 所在页码未知：可先运行 pdftotext 检索 figure 题注进行定位，或逐页快速浏览排查
- 组图（a/b/c 面板）：先完整检视整版布局，随后执行面板裁剪；各面板的边界坐标可借助 zoom 辅助定位
- 扫描版/图片型 PDF：处理流程相同，同样支持直接转图并读取
- 备选：PyMuPDF（当 `python3 -c "import fitz"` 可用时）渲染精度更佳；macOS 平台下的 sips 仅支持首页转换，常规场景一般不予采用
- 若有 ZCode pdf 技能可用，亦可直接调用其提取功能，但不可过度依赖——本技能在设计规范上须确保在脱离该技能的环境中同样具备完整可用性

## 3. 文献链接 / DOI

1. DOI 先行解析：运行 `curl -sL "https://doi.org/10.xxxx/xxxx" -o /dev/null -w '%{url_effective}\n'` 获取出版社落地页
2. **优先走 PMC 开放获取**：使用 Europe PMC / PMC 检索该文章，PMC 全文页中的图版通常支持直接取图（路径常见为 `…/articles/PMC***/bin/***.jpg` 或页面内嵌 `<img>`）；调用 WebFetch 抓取全文页 HTML 并解析图片 URL 后，执行 `curl -A "Mozilla/5.0" -O <url>` 完成下载
3. 出版社页面：通过 WebFetch 获取页面并检索 figure 的图片 URL（各出版社实现不一，注意识别 `data-src` 属性中的懒加载图像）
4. 因付费墙受阻无法取图：切勿强行绕行；应明确告知用户并请求其提供 PDF 或截图，此属规范处理路径而非执行失败

## 4. 微信公众号文章

1. 抓取 HTML：执行 `curl -sL -A "Mozilla/5.0" <url>`；随后调用 Python 解析（利用正则提取，须注意经由 `html.unescape` 还原转义字符）
2. **图片 URL 藏在多个属性里**，须逐一提取并按出现顺序去重：主要包括 `data-src="…"`（最常见之懒加载正文图）、`src="…"` 及 JS 变量 `cdn_url = '…'`。若仅检索 data-src 将遗漏图像
3. **下载用 Python（urllib/requests），不要用 shell `while read` 循环**——输入文件末行若无换行符，`read` 指令将静默跳过最后一条 URL（实践中已有实证教训：曾将该遗漏误判为防盗链）。请求须附带 UA + Referer：

```python
import urllib.request
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
      "Referer": "https://mp.weixin.qq.com/"}
data = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30).read()
```

4. 下载后调用 PIL 打开校验有效性并执行去重（同一张图片可能携带不同参数被重复引用）；运行 `file` 确认真实文件格式（避免 wx_fmt 参数干扰后缀判断），必要时借助 sips 转为 png
5. 若个别图片仍返回 403，进入下方「失败升级阶梯」排查，穷尽手段后方可请用户提供截图

## 5. 其他网页

抓取 HTML 检索 `<img>`（注意识别 `srcset`/`data-src` 等懒加载属性），以 curl + UA 下载；整体处理逻辑同第 3、4 节。

## 6. 追溯原始代码（一手配方，优先级最高）

**图像只是配方的间接证据，原始代码才是事实源。** 只要材料中出现任何代码线索，必须先追溯代码再解剖：

1. **公众号/网页正文内嵌代码**：抓取 HTML 时同步提取正文纯文本——公众号教程常直接附带完整绘图代码（如先前实际案例中整段 R 代码直接内嵌于正文），此类一手配方在优先级上显著高于看图反推
2. **文中提到的 GitHub 仓库**：正文或文末若附有仓库链接 → 调用 GitHub API 遍历文件树检索绘图脚本（`api.github.com/repos/<user>/<repo>/git/trees/main?recursive=1`，脚本文件名多包含 fig/plot 特征），定位后直接以 raw 接口拉取：`raw.githubusercontent.com/<user>/<repo>/main/<path>`
3. **只给了论文没给链接**：先解析 DOI → 在 PMC 全文检索 "Data and code availability" 章节获取仓库 URL（通过 WebFetch 抓取全文页），继而转入第 2 步；外部检索时建议采用"论文标题 + github/code availability"组合词
4. **代码到手后的用法**：程序包名、几何对象、调用参数、主题细节以及数据整形逻辑，一律以代码为唯一基准（例如实际采用的是 ggsankey 而非目测推断的 ggalluvial）；图像仍用于理解排版比例、面板联动关系、图表注释与色彩感知。若代码与图版呈现存在出入（如代码仅为简化版本），须在记录中如实注明各自对应来源
5. **找不到代码是正常结局**：穷尽步骤 1-3 仍无所获，应转回看图反推路径，并在 source.ref 字段如实标注"代码未溯源，配方由图像解剖得出"

## 通用注意

- **失败升级阶梯**：单次取图失败不应视作终局，须按阶梯次序替换方案重试——①换/加请求头（UA、Referer）②换客户端（curl ↔ Python）③换属性/入口（data-src ↔ src ↔ cdn_url；出版社页 ↔ PMC 镜像）④缩小范围重试（只取能取的图）。至少走完 ①②③ 才允许向用户要截图，且要说明试过什么。**先怀疑自己的脚本再怀疑对方**——实践中已有实际案例：因 shell 循环末行无换行符导致漏取 1 张图像，险些将其误判为防盗链
- 图像统一转换为 PNG 格式保存至条目目录，尺寸规范为宽 ≤1600px 且体积 <2MB：可通过 `sips -Z 1600 in.png --out out.png` 或 PIL `thumbnail` 处理
- 记录 source 时如实标注材料类型与出处；他人论文图仅供个人学术参考，不对外分发
- 各来源均存在完全不可获取之客观极限（如受阻于付费墙、数据加密或死链）——在穷尽升级阶梯后，转请用户提供 PDF 或截图属于既定合规路径，而非执行失败
