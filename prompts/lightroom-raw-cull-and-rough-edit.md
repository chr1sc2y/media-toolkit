# RAW Initial Cull And LR/AI Edit Branches

Use this prompt when a photo directory contains a `raw/` folder with RAW files
and optional sibling preview folders such as `hif/`, `jpg/`, or `jpeg/`.

## User Prompt

```text
请对指定照片目录执行 RAW 初筛、全量评级，并准备后续 Lightroom 手工精修。

照片目录：
<PASTE_PHOTO_DIRECTORY_HERE>

范围：
- 如果照片目录尚未整理，先执行媒体整理流程：将 HIF/HEIF/HEIC 放入 hif/，将 RAW 和已有 .xmp sidecar 放入 raw/。
- 初筛阶段处理照片目录下所有 RAW 文件，包括普通照片、portrait/ 分组和 panorama/ 分组里的 RAW。
- 不修改 RAW 本体，不删除文件。
- 将 Lightroom / Camera Raw 可读取的评级结果写入同名 .xmp sidecar。
- 初筛阶段先负责 organize、分组、评级和复核接触表；如果用户没有明确指定 AI 分支、LR+AI 两者都走，或明确要求“只初筛/不粗修”，初筛完成后默认继续走 LR 分支，也就是给 >=3 星 RAW 写入 Lightroom 粗修 XMP 参数。
- 只有用户明确要求只做初筛、只整理、只选图、只评星或不要粗修时，才停在组织、评级和接触表，不进入 LR 或 AI 分支。
- 不写 XMP Label/标签字段；星级 rating 是唯一稳定筛选信号。
- 使用 hif/ 下的 HIF 预览作为识别、分组、构图/清晰度判断和 Contact Sheet 的视觉来源；不要使用 Lightroom 导出的 raw/Export/*.jpg 做人像识别、全景识别、筛选复核或最终 Contact Sheet。
- HIF 是相机已经渲染过的成品预览，不能作为 RAW 最终曝光和调色的唯一依据。曝光统一优先用 rawpy/LibRaw 直接读取 RAW 线性数据和直方图；HIF 只作为视觉辅助。
- 如果有同名 HIF 预览文件，可以用它们辅助判断构图、清晰度、表情和光线，但最终只给 raw/ 里的 RAW 写元数据；如果某张 RAW 被移动到 portrait/ 或 panorama/，对应 raw/Export/*.jpg 只作为关联导出文件随迁，不参与识别或 Contact Sheet。
- 默认分离人像：如果只有一个人，把人像 RAW 放入 portrait/1/raw/，对应 HIF 预览放入 portrait/1/hif/。
- 如果人像里出现多个人，调用视觉判断能力按人物区分，并按首次出现顺序分到 portrait/1/、portrait/2/、portrait/3/ 等目录；每个人物目录内继续保留 raw/ 与 hif/ 分隔。
- 默认分离全景接片素材：识别连续编号、相近曝光/焦段、画面有重叠并明显横向或纵向扫拍的照片组。第一组放入 panorama/1/raw/ 与 panorama/1/hif/，第二组放入 panorama/2/，依此类推；保持每组全景源片完整，不要混入普通风景或人像目录。
- 人像、全景和普通非人像都参与全量评星；不要只给候选照片评级。
- 生成预览时可以使用工具内部临时转换缓存，但流程结束前必须删除；不要把 review_jpg/ 或类似临时转换图留在照片目录。
- 默认输出分离的低分辨率总览图，物理分开保存，方便分别查看，并且使用 mt contact-sheet --hif-only：原照片目录下的 _contact_sheet.jpg 只包含 hif/ 中的普通非人像，且排除 portrait/ 与 panorama/；如果存在人像目录，则 portrait/_contact_sheet.jpg 只来自 portrait/*/hif/，并按 Portrait 1、Portrait 2、Portrait 3 等人物分区；如果存在全景目录，则 panorama/_contact_sheet.jpg 只来自 panorama/*/hif/，并按 Panorama 1、Panorama 2、Panorama 3 等接片组分区。
- 最终 Contact Sheet 的每个缩略图只显示文件名，不显示 001/002 之类的序号；只有明确需要和 manifest.tsv 对照时才启用序号。最后一页只显示实际照片，不用黑图或空白 tile 补齐网格。

筛选规则：
- 使用星级，不使用旗标。
- 5星：最值得精修/发布的主力图。
- 4星：值得留下，进入精修候选。
- 3星：备选图，也进入最终精修候选，但优先级低于 4/5 星。
- 2星：普通记录、重复图、弱构图。
- 1星或0星：明显失败图。
- LR 粗修和 AI 分支都处理所有 >=3星 的照片。

筛选标准：
- 优先选择构图完整、主体明确、光线好、层次好、细节清楚的照片。
- 重复构图只保留最强的几张。
- 同机位、连拍、横向轻微挪动、焦段/构图非常接近的照片必须先按视觉相似度分组；每组通常只保留 1 张 4/5 星主图，最多再保留 1 张 3 星备用。其余重复图即使技术可用，也应降到 2 星 Skip，避免最终精修池被重复构图撑大。
- 3 星是进入最终精修候选的“有价值备选”，不是重复构图的默认收容区。只有构图、主体、瞬间或信息量相对主图有明显差异时，重复组里的次选才给 3 星。
- 对花田、薰衣草、草原花海这类场景，不要只偏向近景花朵或蜜蜂。用户精修偏好显示，大场景花田、行列线条、天空、远山和旅行地点感更重要；近景花/蜜蜂只有在焦点、姿态、背景和信息量都明显强时才进入 3 星以上。
- 风光照重点看天空层次、前景/中景/远景关系、线条引导、河流/山体形态。
- 人像/动物重点看表情、眼神、姿态、清晰度和背景干净程度。
- 宁可少选一点，不要把普通重复图标到4星。

LR 分支：
- 对所有 >=3星 的 RAW 写 Lightroom / Camera Raw 粗修参数。
- 2星及以下只保留初筛评级，不进入默认 LR 粗修。
- 非人像以索尼 ST / Camera ST / Standard 类似的自然色彩作为基础；索尼拍摄的人像优先以索尼 PT / Camera PT 作为基础，如果 Lightroom/ACR 不识别再回退到 Standard/ST 类自然 profile。
- 整体审美偏好：自然但比直出更有层次，颜色可以更好看但不要网红重口；优先保留真实天气、现场氛围和旅行纪录感。
- 可参考 https://photography.prov1dence.top/ 的既有方向：干净、克制、真实氛围优先，避免过度 HDR、过度橙青、过亮阴影或过饱和草地/天空。
- 对于大场景风光，优先保留空气透视、云层压迫感、河流线条和地貌层次，不要把阴天硬修成晴天感。
- 根据 RAW 元数据和 RAW 直方图判断曝光：参考 ISO、快门、光圈、曝光补偿，并优先用 rawpy/LibRaw 读取 RAW 线性亮度分布，让同一批图的整体亮度尽量一致。这里的统一指最终观感统一，不是所有照片写死同一个 Exposure；如果同批照片因为测光、设置或主体亮度不同导致有的过曝、有的欠曝，需要逐张识别并分别调整 Exposure2012、Highlights2012、Shadows2012、Whites2012、Blacks2012，让它们回到统一的亮度和对比基准。
- 执行 LR 分支时，可运行 `mt lr-plan <照片目录> --ratings ">=3"` 生成临时曝光计划；薰衣草、花田、明亮大场景可用 `--style flower`。随后用 `mt lr-apply <照片目录> --ratings ">=3" --style travel-rich` 或 `--style flower-rich` 写入粗修 XMP。`mt lr-apply` 会把 RAW 证据层的 `Exposure2012`、`Highlights2012`、`Shadows2012`、`Whites2012`、`Blacks2012`、`Contrast2012` 和场景风格骨架合并写入 sidecar；必要时再结合 HIF 视觉和题材风格微调。不要跳过 RAW 证据直接凭 HIF 亮度批量写死同一组曝光/高光/阴影参数。写完并验证 XMP 后，删除 `lr_plan.tsv` 和 `raw_stats.tsv`，不要把它们留在照片目录最终状态里。
- 同一批、同一场景/天气下的最终候选图必须保持修图骨架统一：Camera Profile、白平衡基准、高光/阴影策略、Tone Curve、Camera Calibration 范围、HSL/Mixer 上限、暗角策略、锐化策略、镜头校正和 Upright 策略都应一致。只有光线、主体或题材真实变化时才允许单张偏离，并在输出说明里点明。统一修图骨架不等于统一每个滑块数值；曝光/高光/阴影/黑白场要根据 RAW 直方图和 Lightroom 视觉复核逐张校准。
- 保护高光，恢复阴影细节，但不要把阴影抬到发灰；保留自然黑位。
- 增加层次主要依靠 Exposure/Highlights/Shadows/Whites/Blacks、轻微 Tone Curve、局部 Texture/Clarity/Dehaze，而不是直接堆 Saturation/Vibrance。
- 用户的点曲线习惯：优先使用轻微 S 形点曲线来防止死黑和纯白，同时略微增加对比度。黑位可以轻轻抬起或至少避免压死，白位可在高光风险时轻轻压回；下中间调略压、上中间调略提。这个原则合理但应保持克制，按场景微调，不要把某一条具体曲线强行套到所有照片。
- 默认降低鲜艳度和饱和度权重：Vibrance 只做很小幅度调整，Saturation 默认 0 或接近 0；颜色倾向优先通过 Camera Calibration 三原色 Hue/Saturation 做温和微调。
- 哈苏方向的调色目标：更克制的饱和度、更顺滑的高光 roll-off、更厚一点的中间调、更干净的蓝绿分离；不要把它理解成简单加饱和或套滤镜。
- 可以低强度吸收用户 `Sony ST.xmp` 预设的优点：更积极保护高光、保留 Texture 质感、全局 Saturation/Vibrance 保持低值、通过 Camera Calibration 而不是 HSL 饱和度给颜色骨架，并参考它轻微的点曲线 `ToneCurvePV2012=0,0 / 66,59 / 125,125 / 182,188 / 255,255`。但必须限制力度：Highlights2012 通常在 -55 到 -70；Shadows2012 通常 10 到 24；Dehaze 通常 1 到 4；RedSaturation 2 到 4，GreenSaturation 1 到 3，BlueSaturation 0 到 2。不要继承 `PerspectiveUpright=Auto`、`Shadows2012=42`、`Dehaze=8` 或三原色饱和 +11/+12/+12 这种强度。
- 2026-06-09 薰衣草精修反馈：对阳光花田/薰衣草田这类大场景，用户最终风格比 Codex 初稿更亮、更柔、更有颜色骨架。可把高光保护提高到 `Highlights2012=-78..-90`，阴影提高到 `Shadows2012=50..85`，使用负对比 `Contrast2012=-8..-18` 和点曲线 `ToneCurvePV2012=2,5 / 68,55 / 125,124 / 186,193 / 255,250`；三原色校准可在视觉确认后提高到 `RedSaturation=7..10`、`GreenSaturation=9..12`、`BlueSaturation=8..11`，同时保持 `Saturation=0`、`Vibrance=2`，并用 `Blue Saturation=-4..-8` 控制天空。不要把这个强度套到普通阴天草原、人像、雪山、夜景或已经过饱和的场景。
- 长期风格学习是默认工作方式：通常由 agent 做初筛和默认 LR 粗修，用户在 Lightroom 里继续手工精修，之后 agent 对比用户精修后的 `.xmp` 和自己写入的粗修骨架，更新分场景学习方案。不要把用户风格压成一个固定预设；按花田/薰衣草、草原、阴天旅行风光、人像、全景、雪山/高反差山景、夜景/城市等类别逐步维护不同方向。
- 批量粗修阶段的混色器/HSL 只做微调，用来压住草地、水面、天空的过饱和或偏色，不作为主要风格来源；常规范围保持在 Green/Aqua/Blue Saturation 约 -6 到 +4、Green/Yellow Luminance 约 0 到 +5、Blue Luminance 约 -3 到 +2。对于 >=3 星的最终单张精修，可以按预览扩大 HSL 调整，但要避免草地、天空、水面断层或塑料感。
- 裁剪后暗角默认不加：PostCropVignetteAmount=0。只有主体居中、天空大或画面边缘松散的单张风光才考虑极轻微暗角，通常控制在 -1 到 -3；薰衣草/花田这类边缘松散的大场景可在确认不出现明显黑角时用到 -5。全景接片源片不要在合成前加暗角，等合成后再判断。
- 风光可以适量增加 Texture、Clarity、Dehaze。
- 人像/动物减少过强 Clarity/Dehaze，避免毛发和皮肤显脏。

AI 分支：
- 对所有 >=3星 的候选照片生成 AI 成片；不要只处理 4/5 星。
- 不覆盖 RAW、HIF、XMP 或 Lightroom 导出文件。
- AI 输入必须来自 RAW：用 rawpy/LibRaw 从 RAW 渲染全尺寸 sRGB JPG，quality=96，4:4:4/subsampling=0，作为临时中间底图。不要用 Sony HIF 或 Lightroom 导出的 JPG 作为 AI 输入来源。
- 普通照片的临时 AI 输入放在 codex/rawpy_inputs/；人像分组放在 portrait/<person-number>/codex/rawpy_inputs/；全景分组放在 panorama/<sequence-number>/codex/rawpy_inputs/。最终成片、manifest、prompt 记录和接触表确认完成后，删除 rawpy_inputs/，除非用户明确要求保留用于复跑。
- 普通照片的 AI 输出放在照片目录下的 codex/。
- 人像分组的 AI 输出放在 portrait/<person-number>/codex/。
- 全景分组的 AI 输出放在 panorama/<sequence-number>/codex/。
- 每个 codex/ 目录应保留成片接触表 _contact_sheet.jpg；如有 manifest 或 prompt 记录，也放在对应 codex/ 目录内。
- 默认 AI 调色意图：更浓一点的哈苏自然色彩 + 用户 Sony ST 个人风格融合，不要做成很淡的中性调。保持原始构图、透视、焦段观感、地形、道路、栏杆、建筑、水面形状和山脊线；整体仍然真实克制，不做 HDR 或网红重滤镜，但要有更厚的中间调、更明确的高级旅行风光色彩存在感、更积极的高光保护、更干净的蓝/绿/青分离和更稳的草地颜色。参考 `Sony ST.xmp` 的结构：高光保护、轻微 Texture、一定 Dehaze 能量、温和点曲线、通过 Camera Calibration 给颜色骨架，而不是直接堆全局 Saturation/Vibrance；但不要继承自动 Upright、过亮阴影、过强 Dehaze、过强三原色饱和或明显暗角。暗角默认不加或只做几乎不可察觉的轻微边缘收束，不能有明显黑角；保留细节质感但不要过度锐化。
- 天空和光线：纯阴天时只轻微减少云量，增加少量柔和、可信的阳光，必要时露出一点蓝天；避免明显假天空、硬光束、发光边缘、超现实重打光或很重的 AI 味。
- 清理：按需移除路人或明显干扰人物，但不要移除或重塑栏杆、道路、标识、地形、建筑、动物、车辆或其他环境结构，除非用户明确要求。
- 避免塑料质感、过强 Clarity、绿色过饱和、teal-orange 风格、假虚化、焦段变宽、透视改变或边缘大面积 AI 扩图。
- 全景源片不要直接交给 AI 猜测合成。优先 Lightroom Classic Photo Merge > Panorama 生成全景 DNG；如果开源工具已安装且可验证，可使用 Hugin/libpano 工具链（cpfind、autooptimiser、nona、enblend/enfuse）配合 rawpy 渲染的 16-bit TIFF 中间图自动接片。OpenCV Stitcher 只适合低分辨率预览或可行性检查，不作为默认高质量 RAW 全景方案。
- AI 可以处理已经合成的全景成片：做克制调色、去路人、小范围边缘补齐、轻微天空和光线优化。如果全景边缘参差很大，优先裁切或使用 Lightroom boundary warp/fill；AI 只补小缺口，不能大面积重建地形、河流、道路、栏杆、建筑或山体。

LR 分支默认修正：
- 启用镜头配置文件矫正。
- 去除色差。
- 默认不要自动套用 Upright/Level；由模型查看预览后判断是否需要手动小角度旋转（PerspectiveRotate）来校正明显歪斜的水平线。不要为了水平牺牲重要构图，竖拍和带旋转 Orientation 的照片尤其不要盲目自动 Level。
- 白平衡在探索阶段可以保持 As Shot；但同一场景/同一天气下的最终候选图必须检查色彩一致性。若相邻候选图因为相机白平衡解释不同而显得不像同一套编辑，应写入统一的 WhiteBalance=Custom、ColorTemperature 和 Tint。阴天新疆草原/河流场景可用 ColorTemperature=5250、Tint=14 作为中性起点，再按画面微调。
- Tamron 50-400mm F4.5-6.3 A067 拍摄的照片可以写入少量基础锐化，因为这支镜头解析力相对一般；其他镜头默认不额外锐化，除非画面明显需要。
- 普通去杂色通过 Lightroom/ACR 的 Luminance/Color Noise Reduction 元数据滑块实现；这不是 AI Denoise，不会自动生成 DNG。Lightroom 读取元数据后只需要渲染预览，不需要等待额外降噪任务。只有明确使用 Lightroom AI Denoise 时，才需要 Lightroom 执行并等待生成增强文件。
- ISO >= 800 的照片进行温和去杂色/降噪；ISO 越高降噪越强，同时避免涂抹细节。ISO 100-400 默认只保留 ColorNoiseReduction 基础值，不加或少加 LuminanceSmoothing。
- 避免高光溢出、阴影死黑、天空断层、草地/水面过饱和。

XMP 写入建议：
- 初筛阶段给每张 RAW 写入星级 rating；sidecar 文件名必须使用小写 `.xmp`，例如 `DSC08193.ARW` 对应 `DSC08193.xmp`。
- XMP 必须包含 Lightroom/Camera Raw 可识别的 sidecar 标识字段：`crs:HasSettings=True`, `crs:AlreadyApplied=False`, `photoshop:SidecarForExtension=ARW`, `dc:format=image/x-sony-arw`, `xmpMM:PreservedFileName=<RAW filename>`。
- 不写 XMP Label/标签字段。
- LR 分支只对 >=3星 写入基础显影字段；2星及以下默认不写粗修参数，除非用户明确要求。
- 非人像 CameraProfile 优先使用 Camera ST；索尼拍摄的人像优先使用 Camera PT；如果 Lightroom/ACR 不识别，则使用相机/软件可用的 Standard/ST/PT 类自然 profile。
- 镜头矫正字段：LensProfileEnable=1, LensProfileSetup=Auto。
- 去色差字段：AutoLateralCA=1。
- Upright 字段默认关闭：PerspectiveUpright=Off。只有明确需要校正水平时，写入小幅 PerspectiveRotate；不要批量自动 Level。
- 三原色校准使用温和起点，并按题材调整；优先微调 Hue/Saturation，而不是大幅增加 Vibrance/Saturation。默认 Saturation=0，Vibrance 保持低值或接近 0。
- 可以写入轻微 S 曲线、Parametric Tone Curve 或参考 Sony ST 的轻点曲线来增加对比和中间调厚度，但幅度要小，避免压死阴影或高光断层。
- Tamron 50-400mm F4.5-6.3 A067 可写入少量 Sharpness/SharpenRadius/SharpenDetail/SharpenEdgeMasking；其他镜头默认不额外锐化。
- ISO >= 800 的照片可写入更强的 LuminanceSmoothing 和 ColorNoiseReduction。

输出要求：
- 汇总星级数量。
- 列出 >=3星 的文件名。
- 初筛报告说明只写入了 rating 和 sidecar 标识字段，没有写 Label 或 Lightroom 粗修参数。
- 如果执行 LR 分支，说明哪些 Lightroom 字段已经写入，哪些字段可能需要 Lightroom 读入后重新计算或确认，并提醒用户在 Lightroom Classic 中选择 RAW 后执行 `Metadata > Read Metadata from Files`，让 `.xmp` sidecar 生效。
- 如果执行 LR 分支，说明使用了哪个 `mt lr-apply --style` profile；如果用户之后提供手工精修 `.xmp`，需要把它作为该场景类别的学习样本，而不是覆盖所有场景的统一默认值。
- 如果执行 LR 分支，用户读取元数据后，如果是新风格试调或大批量粗修，需要对应用后的效果做二次 Review：检查方向、自动水平/裁切、主体构图、曝光一致性、阴影是否发灰、颜色是否过饱和、Texture/Clarity/Dehaze 是否显脏。竖拍和带旋转 Orientation 的照片不要盲目启用自动 Level。
- 如果执行 AI 分支，列出各个 codex/ 输出目录、生成数量、manifest/prompt 记录和 codex/_contact_sheet.jpg 路径。
- 说明是否存在 portrait 目录，以及每个人像编号目录的 RAW/HIF 数量。
- 说明是否存在 panorama 目录，以及每个全景编号目录的 RAW/HIF 数量。
- 确认临时 review_jpg/ 已删除。
- 确认临时 `lr_plan.tsv` 和 `raw_stats.tsv` 已删除。
- 如果生成了接触表，说明原目录 _contact_sheet.jpg、portrait/_contact_sheet.jpg、panorama/_contact_sheet.jpg 的位置；不存在某类目录时不要编造对应接触表。

后续只有两个用户面对的流程：
- 初筛：本提示词负责的组织、评级、接触表和默认 LR 粗修；只有明确要求只初筛时才不写 LR 粗修参数。
- 成片归档：用户在 Lightroom 手工精修并导出最终 JPG 后，运行 `mt finalize <照片目录> --scene <场景类别>`。该流程以 Lightroom 导出文件为最终名单：根目录 `raw/Export/` 和 `portrait/<n>/raw/Export/` 里的文件名 stem 决定要归档哪些原始 HIF；然后从根目录 `hif/` 和 `portrait/<n>/hif/` 复制匹配 HIF 到照片目录自己的 `featured/`。它不复制 Lightroom 导出文件本身，不把 `panorama/<n>/hif/` 里的全景源片 HIF 复制进目标目录，不写本地 style learning 报告。如果最终 `.xmp` 暴露出新的用户风格规律，应直接更新仓库 profile、preset notes、prompt 和记忆。不要把风格学习作为第三个独立流程，也不要再要求用户单独“提取 featured”；以后称为“成片归档”。Lightroom 生成的 `*-Pano.dng` 没有对应 HIF 是正常的，不需要报告为问题。
```

## Usage

Open this repository, then ask the agent to use this prompt against a photo
directory:

```text
使用 prompts/lightroom-raw-cull-and-rough-edit.md
对 /path/to/photo-directory 执行 RAW 初筛、评级和 LR/AI 分支流程。
```

Keep photos in their original travel/import directory. Do not copy large photo
folders into this repository.
