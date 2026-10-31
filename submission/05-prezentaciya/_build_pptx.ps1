$ErrorActionPreference = "Stop"
$out = "D:\PythonProject_PI\8\PEf05_FinalProject\navigator\submission\05-prezentaciya\Navigator.pptx"
$pp = New-Object -ComObject PowerPoint.Application
$pres = $pp.Presentations.Add()
$pres.PageSetup.SlideWidth = [single]960
$pres.PageSetup.SlideHeight = [single]540

function C([int]$r, [int]$g, [int]$b) { return $r + ($g * 256) + ($b * 65536) }
$ink = C 16 38 44
$paper = C 231 242 236
$deep = C 14 42 51
$amber = C 230 162 60
$steel = C 31 111 138
$muted = C 78 101 108
$card = C 247 251 248
$light = C 231 242 236

function Add-Rect($slide, $x, $y, $w, $h, $fill) {
  $shape = $slide.Shapes.AddShape(1, [single]$x, [single]$y, [single]$w, [single]$h)
  $shape.Fill.ForeColor.RGB = $fill
  $shape.Line.Visible = 0
  return $shape
}
function Add-Tx($slide, $x, $y, $w, $h, $text, $size, $color, $font, $bold) {
  $box = $slide.Shapes.AddTextbox(1, [single]$x, [single]$y, [single]$w, [single]$h)
  $box.TextFrame.WordWrap = -1
  $box.TextFrame.AutoSize = 0
  $box.TextFrame.MarginLeft = [single]0
  $box.TextFrame.MarginRight = [single]0
  $box.TextFrame.MarginTop = [single]0
  $range = $box.TextFrame.TextRange
  $range.Text = $text
  $range.Font.Name = $font
  $range.Font.Size = [single]$size
  $range.Font.Bold = [int]$bold
  $range.Font.Color.RGB = $color
  $range.ParagraphFormat.SpaceWithin = [single]1
  return $box
}
function Set-Bg($slide, $color) {
  $slide.FollowMasterBackground = 0
  $slide.Background.Fill.Solid()
  $slide.Background.Fill.ForeColor.RGB = $color
}
function Add-Horizon($slide, $x, $y, $dark) {
  Add-Rect $slide $x $y 150 8 $amber | Out-Null
  Add-Rect $slide ($x + 150) $y 150 8 (C 126 182 201) | Out-Null
  $label = $(if ($dark) { $light } else { $muted })
  Add-Tx $slide $x ($y + 12) 150 18 "Личная практика" 11 $label "Segoe UI" 0 | Out-Null
  $right = Add-Tx $slide ($x + 150) ($y + 12) 150 18 "1С-Премиум" 11 $(if ($dark) { $light } else { $steel }) "Segoe UI" 0
  $right.TextFrame.TextRange.ParagraphFormat.Alignment = 3
}
function Add-FootLink($slide, $label, $url, $num) {
  $box = Add-Tx $slide 48 508 760 22 $label 14 $steel "Segoe UI" 0
  $box.TextFrame.TextRange.Font.Underline = -1
  $box.TextFrame.TextRange.ActionSettings(1).Hyperlink.Address = $url
  $n = Add-Tx $slide 860 508 52 18 $num 12 $muted "Segoe UI" 0
  $n.TextFrame.TextRange.ParagraphFormat.Alignment = 3
}
function Add-Foot($slide, $left, $num, $dark) {
  $color = $(if ($dark) { (C 157 180 188) } else { $muted })
  Add-Tx $slide 48 508 640 18 $left 12 $color "Segoe UI" 0 | Out-Null
  $n = Add-Tx $slide 860 508 52 18 $num 12 $color "Segoe UI" 0
  $n.TextFrame.TextRange.ParagraphFormat.Alignment = 3
}

$s = $pres.Slides.Add(1, 12); Set-Bg $s $deep
Add-Tx $s 48 36 700 20 "ВЫПУСКНОЙ ПРОЕКТ  ·  31 ОКТЯБРЯ 2026" 13 $amber "Bahnschrift" 0 | Out-Null
Add-Tx $s 48 78 800 80 "Навигатор" 60 $light "Bahnschrift" 1 | Out-Null
Add-Horizon $s 48 175 $true
Add-Tx $s 48 240 760 90 "Telegram-ассистент отвечает по двум публичным сайтам и не смешивает их цены." 24 $light "Segoe UI" 0 | Out-Null
Add-Foot $s "Приколота Александр Фёдорович" "ТЗ v1.3" $true

$s = $pres.Slides.Add(2, 12); Set-Bg $s $paper
Add-Tx $s 48 32 700 18 "ПРОБЛЕМА" 13 $steel "Bahnschrift" 0 | Out-Null
Add-Tx $s 48 56 860 80 "Один вопрос, два контура, ответ человека — в рабочий день" 28 $ink "Bahnschrift" 1 | Out-Null
$cards = @(
  @("Вечер и выходной", "На сайте написано, что Александр отвечает в течение рабочего дня. Между встречами вопрос уже лежит на странице."),
  @("Два сайта", "Опыт и вилка консультации — на komfortnavigator.ru. Каталог поддержки — на 1c-prem.ru."),
  @("Легко смешать", "5 000–15 000 ₽ — личная консультация. Цены ООО «1С-Премиум» на сайте нет, и бот их не сочиняет.")
)
$colors = @($amber, $steel, $deep)
for ($i = 0; $i -lt 3; $i++) {
  $x = 48 + ($i * 296)
  Add-Rect $s $x 180 280 8 $colors[$i] | Out-Null
  Add-Rect $s $x 188 280 250 $card | Out-Null
  Add-Tx $s ($x + 16) 206 248 40 $cards[$i][0] 18 $ink "Bahnschrift" 1 | Out-Null
  Add-Tx $s ($x + 16) 250 248 160 $cards[$i][1] 15 $ink "Segoe UI" 0 | Out-Null
}
Add-Foot $s "Навигатор" "2" $false

$s = $pres.Slides.Add(3, 12); Set-Bg $s $paper
Add-Tx $s 48 32 700 18 "РЕШЕНИЕ" 13 $steel "Bahnschrift" 0 | Out-Null
Add-Tx $s 48 56 860 50 "Один бот. Три исхода." 32 $ink "Bahnschrift" 1 | Out-Null
$cards = @(
  @("Ответ со ссылкой", "Поиск по базе и не больше трёх URL. Если вопрос путает контуры, оба названы своими именами."),
  @("Честный отказ", "Нет опоры — фиксированная фраза. Сумма, которой нет в личном фрагменте, до чата не доходит."),
  @("Заявка", "Имя, компания, роль, задача и согласие. Карточка уходит владельцу даже без OpenAI.")
)
for ($i = 0; $i -lt 3; $i++) {
  $x = 48 + ($i * 296)
  Add-Rect $s $x 150 280 8 $colors[$i] | Out-Null
  Add-Rect $s $x 158 280 280 $card | Out-Null
  Add-Tx $s ($x + 16) 178 248 36 $cards[$i][0] 18 $ink "Bahnschrift" 1 | Out-Null
  Add-Tx $s ($x + 16) 224 248 180 $cards[$i][1] 16 $ink "Segoe UI" 0 | Out-Null
}
Add-Foot $s "Кнопки меню идут в тот же поиск" "3" $false

$s = $pres.Slides.Add(4, 12); Set-Bg $s $paper
Add-Tx $s 48 32 700 18 "КАК УСТРОЕНО" 13 $steel "Bahnschrift" 0 | Out-Null
Add-Tx $s 48 56 860 46 "Сначала ворота, потом модель" 32 $ink "Bahnschrift" 1 | Out-Null
$steps = @(
  @("1", "Телефон и почта маскируются до вектора"),
  @("2", "PostgreSQL: смысл и точные слова, фильтр контура"),
  @("3", "Порог 0,30. Ниже него модель молчит"),
  @("4", "gpt-6-sol видит только фрагменты, усилие low"),
  @("5", "Сумма сверяется с личным контуром"),
  @("6", "Текст и источники в Telegram. Заявка остаётся в РФ")
)
for ($i = 0; $i -lt 6; $i++) {
  $x = 36 + ($i * 152)
  Add-Rect $s $x 160 144 250 $deep | Out-Null
  Add-Tx $s ($x + 12) 176 120 36 $steps[$i][0] 26 $amber "Bahnschrift" 1 | Out-Null
  Add-Tx $s ($x + 12) 220 120 160 $steps[$i][1] 14 $light "Segoe UI" 0 | Out-Null
}
Add-Foot $s "Python 3.12 · aiogram 3 · pgvector · text-embedding-3-small" "4" $false

$s = $pres.Slides.Add(5, 12); Set-Bg $s $paper
Add-Tx $s 48 32 700 18 "ДЕМО" 13 $steel "Bahnschrift" 0 | Out-Null
Add-Tx $s 48 56 860 46 "Эти вопросы уже прогнаны" 32 $ink "Bahnschrift" 1 | Out-Null
$qs = @(
  "1   Сколько стоит часовая консультация?",
  "2   Первая встреча платная?",
  "3   Какой сертификат по управлению проектами?",
  "4   Вы внедряли 1С:Управление холдингом?",
  "5   Вы сейчас работаете в ООО «1С-Премиум»?"
)
Add-Tx $s 48 130 560 280 ($qs -join "`r") 20 $ink "Segoe UI" 0 | Out-Null
Add-Tx $s 630 130 280 24 "ЛОВУШКИ" 13 $steel "Bahnschrift" 0 | Out-Null
$traps = "Цена сопровождения «1С-Премиум» в месяц`r`rЧасы SLA по КПТР для «нашей базы»`r`rДомашний телефон и дата рождения`r`rЛицензия 1С:ERP — этого в базе нет"
Add-Tx $s 630 164 290 250 $traps 18 $ink "Segoe UI" 0 | Out-Null
Add-FootLink $s "t.me/AI_KomfortNavigator_bot   ·   ответы 3–7 секунд" "https://t.me/AI_KomfortNavigator_bot" "5"

$s = $pres.Slides.Add(6, 12); Set-Bg $s $paper
Add-Tx $s 48 32 700 18 "БАЗА И ГРАНИЦЫ" 13 $steel "Bahnschrift" 0 | Out-Null
Add-Tx $s 48 56 860 80 "13 документов. Даты больше не спорят." 32 $ink "Bahnschrift" 1 | Out-Null
Add-Tx $s 48 160 520 200 "Шесть карточек личной практики и семь — компании. В индексе 54 фрагмента.`r`r31.10.2026 резюме переснято. Страница и PDF пишут одно: ООО «1С-Премиум», июль 2024 — настоящее время." 18 $ink "Segoe UI" 0 | Out-Null
$bounds = "Не фирма «1С» и не право подписи`r`rОферту не превращает в новые обязательства`r`rЧасы SLA не выдумывает`r`rСемью и домашний телефон не переносит"
Add-Tx $s 600 160 310 240 $bounds 18 $ink "Segoe UI" 0 | Out-Null
Add-Foot $s "Порог сходства после прогона: 0,30" "6" $false

$s = $pres.Slides.Add(7, 12); Set-Bg $s $paper
Add-Tx $s 48 32 800 18 "ЭКОНОМИКА  ·  КУРС 80,6761 ₽" 13 $steel "Bahnschrift" 0 | Out-Null
Add-Tx $s 48 56 860 46 "Сколько списывается со счёта" 32 $ink "Bahnschrift" 1 | Out-Null
Add-Tx $s 48 130 420 24 "Касса в месяц при 30 диалогах в сутки" 14 $muted "Segoe UI" 0 | Out-Null
Add-Tx $s 48 158 420 70 "4 104 ₽" 48 $ink "Bahnschrift" 1 | Out-Null
Add-Tx $s 48 240 440 180 "API gpt-6-sol около 36 USD, это 2 904 ₽. Строка VPS 1 200 ₽ — оценка отдельной машины. Сейчас бот на сервере сайта. На 100 USD генерация останавливается, заявка остаётся." 16 $ink "Segoe UI" 0 | Out-Null
$year = "Год, касса с буфером 20% — 59 102 ₽`r`rГод с трудом автора — 419 102 ₽`r`rБот для клиента — 0 ₽`r`rКасса года — 12 консультаций по 5 000 ₽"
Add-Tx $s 540 150 370 220 $year 18 $ink "Segoe UI" 0 | Out-Null
Add-Foot $s "Пик 80 диалогов — около 8 864 ₽ кассы в месяц" "7" $false

$s = $pres.Slides.Add(8, 12); Set-Bg $s $paper
Add-Tx $s 48 32 700 18 "ДАЛЬШЕ" 13 $steel "Bahnschrift" 0 | Out-Null
Add-Tx $s 48 56 860 46 "Уже на сервере сайта" 32 $ink "Bahnschrift" 1 | Out-Null
$next = @(
  @("Где", "147.45.150.56, рядом с komfortnavigator.ru. Отдельный Compose, база только на localhost. После перезагрузки поднимается сам."),
  @("OpenAI", "Официальный API. Московский адрес дата-центра закрыт, выход через 72.56.100.17. Заявка остаётся в России."),
  @("Дальше", "Пилот 5–10 человек и журнал 14 дней. Оплата, КП компании, календарь и виджет в эту версию не входят.")
)
for ($i = 0; $i -lt 3; $i++) {
  $x = 48 + ($i * 296)
  Add-Rect $s $x 150 280 8 $colors[$i] | Out-Null
  Add-Rect $s $x 158 280 270 $card | Out-Null
  Add-Tx $s ($x + 16) 176 248 36 $next[$i][0] 18 $ink "Bahnschrift" 1 | Out-Null
  Add-Tx $s ($x + 16) 220 248 180 $next[$i][1] 16 $ink "Segoe UI" 0 | Out-Null
}
Add-FootLink $s "t.me/AI_KomfortNavigator_bot" "https://t.me/AI_KomfortNavigator_bot" "8"

$pdf = $out -replace '\.pptx$', '.pdf'
if (Test-Path $out) { Remove-Item $out -Force }
if (Test-Path $pdf) { Remove-Item $pdf -Force }
$pres.SaveAs($out, 24)
$pres.SaveAs($pdf, 32)
$pres.Close()
$pp.Quit()
Write-Output "pptx-ok"
