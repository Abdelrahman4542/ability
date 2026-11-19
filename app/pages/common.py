from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QFrame

def page_header(title, description, eyebrow="ABILITYBRIDGE AI"):
    box = QWidget()
    layout = QVBoxLayout(box)
    layout.setContentsMargins(0, 0, 0, 18)
    tag = QLabel(eyebrow.upper())
    tag.setObjectName("BrandAccent")
    title_label = QLabel(title)
    title_label.setObjectName("PageTitle")
    desc = QLabel(description)
    desc.setObjectName("PageSubtitle")
    desc.setWordWrap(True)
    layout.addWidget(tag)
    layout.addWidget(title_label)
    layout.addWidget(desc)
    return box

def panel(object_name="Panel"):
    frame = QFrame()
    frame.setObjectName(object_name)
    return frame
