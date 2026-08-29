# 从各类材料中获取 figure 图像

模式 A 第一步。目标都是一样的：拿到可以细看的图片文件（PNG/JPG）。以下命令已在本机验证过可用性，遇到工具缺失时按文内备选方案降级。

拿到图像后一律先用 Read 查看，小字/小面板先裁剪放大成局部图再读，确认细节后进入解剖步骤。

## 1. 本地图片 / 截图

直接 Read 该文件即可，无需转换。若同时给的是整版多面板截图，先原样阅读，解剖时逐面板看；需要把单个面板存为独立条目的 reference 时用 PIL 裁剪：

```bash
python3 -c "
from PIL import Image
im = Image.open('输入.png')
im.crop((left, top, right, bottom)).save('面板.png')  # 像素坐标按显示比例换算
"
```

## 2. PDF（论文、补充材料）

先用 pdftoppm 把目标页转成 PNG（200dpi 起步，保证小字可读），再用 PIL 裁出 figure 区域：

```bash
pdftoppm -png -r 200 -f 5 -l 5 paper.pdf page    # 第5页 → page-5.png
```

- 不知道 figure 在哪页：pdftotext 搜 figure 标题定位，或逐页快速浏览
- 组图（a/b/c 面板）：整版先读一遍，再按面板裁剪；面板坐标用 zoom 辅助定位
- 扫描版/图片型 PDF：同样能转图，直接用
- 备选：PyMuPDF（`python3 -c "import fitz"` 可用时）渲染更精细；macOS 上 sips 只能转第一页，一般不用
- 有 ZCode pdf 技能可用时，也可以用它提取，但不要依赖它——本技能要求在无该技能的环境同样可用

## 3. 文献链接 / DOI

1. DOI 先解析：`curl -sL "https://doi.org/10.xxxx/xxxx" -o /dev/null -w '%{url_effective}\n'` 拿到出版社落地页
2. **优先走 PMC 开放获取**：用 Europe PMC / PMC 检索该文章，PMC 全文页的图片通常可直接取（`…/articles/PMC***/bin/***.jpg` 或页面内 `<img>`）；WebFetch 全文页 HTML 后找图片 URL，`curl -A "Mozilla/5.0" -O <url>` 下载
3. 出版社页面：WebFetch 页面找 figure 的图片 URL（各出版社不同，注意懒加载图在 `data-src` 属性里）
4. 付费墙拿不到图：不要硬绕。明确告诉用户，请其提供 PDF 或截图，这是正常路径而非失败

## 4. 微信公众号文章

1. 抓 HTML：`curl -sL -A "Mozilla/5.0" <url>`；用 Python 解析（正则提取，注意 `html.unescape`）
2. **图片 URL 藏在多个属性里**，逐一提取并按出现顺序去重：`data-src="…"`（懒加载正文图，最常见）、`src="…"`、JS 变量 `cdn_url = '…'`。只看 data-src 会漏图
3. **下载用 Python（urllib/requests），不要用 shell `while read` 循环**——文件末行无换行符时 `read` 会静默跳过最后一条 URL（已实际踩坑：把防盗链误判为失败原因）。带 UA + Referer：

```python
import urllib.request
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
      "Referer": "https://mp.weixin.qq.com/"}
data = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30).read()
```

4. 下载后用 PIL 打开校验并去重（同一张图可能以不同参数重复引用）；`file` 确认真实格式（wx_fmt 参数会混淆后缀），必要时 sips 转 png
5. 个别图片仍 403 时进入下方「失败升级阶梯」，最后手段才是请用户截图

## 5. 其他网页

抓 HTML 找 `<img>`（注意 `srcset`/`data-src` 懒加载），curl + UA 下载；同 3、4 的处理。

## 6. 追溯原始代码（一手配方，优先级最高）

**图像只是配方的间接证据，原始代码才是事实源。** 只要材料中出现任何代码线索，必须先追溯代码再解剖：

1. **公众号/网页正文内嵌代码**：抓 HTML 时同时提取正文纯文本——公众号教程常直接贴完整绘图代码（本次案例：整段 R 代码内嵌在正文里），这就是一手配方，优先级高于看图反推
2. **文中提到的 GitHub 仓库**：正文/文末出现仓库链接 → 用 GitHub API 列文件树找绘图脚本（`api.github.com/repos/<user>/<repo>/git/trees/main?recursive=1`，脚本名常含 fig/plot），raw 拉取：`raw.githubusercontent.com/<user>/<repo>/main/<path>`
3. **只给了论文没给链接**：先解 DOI → PMC 全文找 "Data and code availability" 里的仓库 URL（WebFetch 全文页），再回到第 2 步；搜索时用"论文标题 + github/code availability"组合词
4. **代码到手后的用法**：包名、几何对象、参数、主题细节、数据整形逻辑一律以代码为准（如实际用的是 ggsankey 而非肉眼猜的 ggalluvial）；图像仍用于排版比例、面板联动、注释与配色观感的理解。代码与图有出入时（如代码是简化版）在记录里注明各自来源
5. **找不到代码是正常结局**：穷尽 1-3 后没有，就回到看图反推，source.ref 如实写"代码未溯源，配方由图像解剖得出"

## 通用注意

- **失败升级阶梯**：取图失败不算终局，按阶梯换方法重试——①换/加请求头（UA、Referer）②换客户端（curl ↔ Python）③换属性/入口（data-src ↔ src ↔ cdn_url；出版社页 ↔ PMC 镜像）④缩小范围重试（只取能取的图）。至少走完 ①②③ 才允许向用户要截图，且要说明试过什么。**先怀疑自己的脚本再怀疑对方**——本次实际案例：shell 循环末行无换行导致漏下 1 张，险些误判为防盗链
- 图像统一转成 PNG 存条目目录，宽 ≤1600px、<2MB：`sips -Z 1600 in.png --out out.png` 或 PIL `thumbnail`
- 记录 source 时如实标注材料类型与出处；他人论文图仅作个人学习参考，不对外分发
- 各来源都可能彻底拿不到（付费墙、加密、彻底坏链）——穷尽阶梯后请用户提供 PDF/截图是正常路径而非失败
