# Lightroom RAW Cull And Rough Edit

Use this prompt when a photo directory contains a `raw/` folder with RAW files
and optional sibling preview folders such as `hif/`, `jpg/`, or `jpeg/`.

## User Prompt

```text
请对指定照片目录执行 Lightroom / Camera Raw 前置筛选和粗修流程。

照片目录：
<PASTE_PHOTO_DIRECTORY_HERE>

范围：
- 只处理照片目录下 raw/ 里的 RAW 文件。
- 不修改 RAW 本体，不删除文件。
- 将 Lightroom / Camera Raw 可读取的结果写入同名 .xmp sidecar。
- 如果有同名 hif/jpg/jpeg 预览文件，可以用它们辅助判断构图、清晰度、表情和光线，但最终只给 raw/ 里的 RAW 写元数据。

筛选规则：
- 使用星级，不使用旗标。
- 5星：最值得精修/发布的主力图。
- 4星：值得留下，进入精修候选。
- 3星：备选图，不进入默认精修。
- 2星：普通记录、重复图、弱构图。
- 1星或0星：明显失败图。
- 我最终会筛选并精修 >=4星 的照片。

筛选标准：
- 优先选择构图完整、主体明确、光线好、层次好、细节清楚的照片。
- 重复构图只保留最强的几张。
- 风光照重点看天空层次、前景/中景/远景关系、线条引导、河流/山体形态。
- 人像/动物重点看表情、眼神、姿态、清晰度和背景干净程度。
- 宁可少选一点，不要把普通重复图标到4星。

粗修风格：
- 以索尼 ST / Camera ST / Standard 类似的自然色彩作为基础。
- 整体审美偏好：自然但比直出更有层次，颜色可以更好看但不要网红重口；优先保留真实天气、现场氛围和旅行纪录感。
- 对于大场景风光，优先保留空气透视、云层压迫感、河流线条和地貌层次，不要把阴天硬修成晴天感。
- 做统一曝光，让整组亮度更一致。
- 保护高光，恢复阴影细节。
- 适量增加对比度、自然饱和度和整体观感。
- 可以适当增加三原色饱和度/校准感，但不要过度艳丽；默认用温和起点，除非画面需要，不要把三原色饱和度推得很重。
- 风光可以适量增加 Texture、Clarity、Dehaze。
- 人像/动物减少过强 Clarity/Dehaze，避免毛发和皮肤显脏。

默认修正：
- 启用镜头配置文件矫正。
- 去除色差。
- 默认尝试自动水平/Level Upright；不要为了水平牺牲重要构图。
- 白平衡默认保持 As Shot，除非明显偏色。
- 不默认额外锐化；锐化留到精修、降噪之后或按输出尺寸处理。
- ISO >= 800 的照片进行去杂色/降噪；ISO 越高降噪越强，同时避免涂抹细节。
- 避免高光溢出、阴影死黑、天空断层、草地/水面过饱和。

XMP 写入建议：
- 给每张 RAW 写入星级、标签和基础显影参数。
- >=4星 的照片标签设为 Select。
- 3星标签设为 Maybe。
- 2星及以下标签设为 Skip。
- 对所有照片应用基础预设字段，不只应用到 >=4星，因为后期可能会把 2/3 星照片重新标成 4/5 星。
- CameraProfile 优先使用 Camera ST；如果 Lightroom/ACR 不识别，则使用相机/软件可用的 Standard/ST 类自然 profile。
- 镜头矫正字段：LensProfileEnable=1, LensProfileSetup=Auto。
- 去色差字段：AutoLateralCA=1。
- 自动水平字段：PerspectiveUpright=Level。
- 三原色饱和度使用温和起点，例如 RedSaturation=4, GreenSaturation=3, BlueSaturation=4；这不是最佳值，只是安全起点，按照片题材可调。
- 不写入 Sharpness/SharpenRadius/SharpenDetail/SharpenEdgeMasking，除非用户明确要求。
- ISO >= 800 的照片可写入更强的 LuminanceSmoothing 和 ColorNoiseReduction。

输出要求：
- 汇总星级数量。
- 列出 >=4星 的文件名。
- 说明哪些 Lightroom 字段已经写入，哪些字段可能需要 Lightroom 读入后重新计算或确认。
```

## Usage

Open this repository, then ask the agent to use this prompt against a photo
directory:

```text
使用 prompts/lightroom-raw-cull-and-rough-edit.md
对 /path/to/photo-directory 执行 RAW 初筛和 Lightroom 粗修流程。
```

Keep photos in their original travel/import directory. Do not copy large photo
folders into this repository.

