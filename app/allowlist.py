"""Публичные страницы из раздела 5.1 ТЗ версии 1.2. Другие URL в обход не входят."""

ALLOWLIST = (
    "https://komfortnavigator.ru/",
    "https://komfortnavigator.ru/offer",
    "https://komfortnavigator.ru/privacy",
    "https://komfortnavigator.ru/Prikolota_Aleksandr_CV_2026.pdf",
    "https://www.1c-prem.ru/",
    "https://1c-prem.ru/services/",
    "https://1c-prem.ru/about/",
    "https://1c-prem.ru/services/optimizatsiya-proizvoditelnosti/",
    "https://1c-prem.ru/services/audit-monitoring-soprovozhdenie-sistem/",
    "https://www.1c-prem.ru/services/rabota-s-intsidentami/",
    "https://www.1c-prem.ru/articles/zachem-biznesu-svoy-tsentr-kompetentsii-1s-vzglyad-iznutri/",
    "https://www.1c-prem.ru/articles/vaybkoding-v-1s-ot-eksperimenta-k-upravlyaemoy-praktike/",
)

REFUSAL = (
    "В опубликованных материалах сайтов у меня нет достаточных сведений, чтобы ответить точно. "
    "Я не буду додумывать. Могу передать вопрос Александру: он отвечает в течение рабочего дня. "
    "Напишите, как к вам обращаться и в чём задача, или нажмите «Оставить заявку»."
)

PUBLIC_CONTACTS = "aleksandrfprikolota@gmail.com и +7 (903) 775-50-48"

UNAVAILABLE = (
    "Сейчас не могу ответить по базе. "
    f"Напишите Александру: {PUBLIC_CONTACTS}. "
    "Заявку можно оставить кнопкой «Оставить заявку»: она не зависит от модели."
)

BUDGET_STOP = (
    "Месячный лимит ответов по базе на этот календарный месяц исчерпан. "
    f"Заявку оставить можно, либо напишите {PUBLIC_CONTACTS}."
)

DISCLAIMER = (
    "Навигатор отвечает по публичным материалам сайтов komfortnavigator.ru и 1c-prem.ru. "
    "Он не заменяет консультацию и не готовит коммерческое предложение ООО «1С-Премиум»."
)
