# editor.py (v2.14.2 - 파싱된 스탯 툴팁 표시)
import sys
import json
import os
import uuid
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
                             QPushButton, QLabel, QListWidget, QListWidgetItem,
                             QLineEdit, QTabWidget, QSplitter, QMessageBox,
                             QFormLayout, QDialog, QDialogButtonBox, QScrollArea,
                             QComboBox)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QShortcut, QKeySequence

# --- 경로 설정 및 상수 (이전과 동일) ---
def get_datafile_path(relative_path):
    if getattr(sys, 'frozen', False): base_path = os.path.dirname(sys.executable)
    else: base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)
GAMEDATA_FILE = get_datafile_path('gamedata.json')
USERDECKS_FILE = get_datafile_path('user_decks.json')
STYLE_TYPES = [("main1", "메인유파1"), ("main2", "메인유파2"), ("main_common", "메인공용"), ("support1", "지원유파1"), ("support2", "지원유파2"), ("support_common", "지원공용")]
ATTRIBUTES = ["빛", "어둠", "땅", "불", "물", "바람"]
RARITIES = ["5성", "4성"]
ATTRIBUTE_ORDER = {"빛": 0, "어둠": 1, "땅": 2, "불": 3, "물": 4, "바람": 5}
STAT_TYPES = ["공격력 %", "공격력 고정", "스킬 피해 %", "일반 공격 피해 %", "치명타 확률 %", "치명타 피해 %", "추가 피해 %", "불 속성 피해 %", "물 속성 피해 %", "바람 속성 피해 %", "땅 속성 피해 %", "빛 속성 피해 %", "어둠 속성 피해 %", "공격 속도 %", "이동 속도 %", "방어력 %", "방어력 고정", "받는 피해 감소 %", "적 방어력 감소 %", "적 속성 저항 감소 %"]

# --- (★신규★) tracker.py의 DataParser 클래스를 그대로 복사 ---
class DataParser:
    def __init__(self):
        self.data = {}; self.load_data_files()
    def load_data_files(self):
        files_to_load = ["HitDamage", "EffectValue", "OnceAdditionalAttributeValue", "BuffValue", "ScriptParameterValue"]
        for filename in files_to_load:
            try:
                path = get_datafile_path(f'{filename}.json')
                with open(path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if content: self.data[filename] = json.loads(content)
                    else: self.data[filename] = {}
            except (FileNotFoundError, json.JSONDecodeError): self.data[filename] = {}
    def parse_param(self, param_str):
        parts = param_str.split(',');
        if len(parts) < 3: return None
        table_name, record_id = parts[0], parts[2]
        if table_name not in self.data or record_id not in self.data[table_name]: return None
        record = self.data[table_name][record_id]; stat_name = f"{table_name} 효과"; value = 0.0
        try:
            if table_name == "HitDamage": stat_name = "스킬 피해 %"; value = float(record.get("SkillPercentAmend", [0])[0]) / 10000.0
            elif table_name in ["EffectValue", "BuffValue"]: stat_name = "효과값 %"; value = float(record.get("EffectTypeParam1", "0.0")) * 100.0
            elif table_name == "OnceAdditionalAttributeValue": stat_name = "추가 스탯 %"; value = float(record.get("Value1", 0)) / 100.0
            elif table_name == "ScriptParameterValue": stat_name = "특수 조건 값"; value = float(record.get("CommonData", 0)) / 10000.0
            else: return None
        except (ValueError, TypeError): return None
        return {"type": stat_name, "value": value}

# --- 팝업 클래스들 (이전과 동일) ---
# ... (생략)
class PotentialDialog(QDialog):
    def __init__(self, title, defaults=None, parent=None):
        super().__init__(parent); self.setWindowTitle(title); self.setMinimumWidth(500); main_layout = QVBoxLayout(self); form_layout = QFormLayout(); self.inputs = {}; defaults = defaults or {}; self.inputs['name'] = QLineEdit(defaults.get('name', '')); form_layout.addRow(QLabel("이름:"), self.inputs['name']); self.effects_layout = QVBoxLayout(); self.effect_widgets = [];
        for effect in defaults.get('effects', []): self.add_effect_line(effect.get("type"), str(effect.get("value", "0")))
        add_effect_btn = QPushButton("효과 추가 (+)"); add_effect_btn.clicked.connect(lambda: self.add_effect_line()); effects_group_box = QWidget(); group_layout = QVBoxLayout(effects_group_box); group_layout.setContentsMargins(0,0,0,0); group_layout.addLayout(self.effects_layout); group_layout.addWidget(add_effect_btn, 0, Qt.AlignmentFlag.AlignRight); form_layout.addRow(QLabel("스탯 효과:"), effects_group_box);
        self.params_layout = QVBoxLayout(); self.param_widgets = []
        for param_text in defaults.get('params', []): self.add_param_line(param_text)
        add_param_btn = QPushButton("원본 Param 추가 (+)"); add_param_btn.clicked.connect(lambda: self.add_param_line()); params_group_box = QWidget(); group_layout_p = QVBoxLayout(params_group_box); group_layout_p.setContentsMargins(0,0,0,0); group_layout_p.addLayout(self.params_layout); group_layout_p.addWidget(add_param_btn, 0, Qt.AlignmentFlag.AlignRight); form_layout.addRow(QLabel("원본 데이터 (참고용):"), params_group_box);
        main_layout.addLayout(form_layout); button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel); button_box.accepted.connect(self.accept); button_box.rejected.connect(self.reject); main_layout.addWidget(button_box)
    def add_effect_line(self, type_str=None, value_str=""):
        line_layout = QHBoxLayout(); type_combo = QComboBox(); type_combo.addItems(STAT_TYPES);
        if type_str and type_str in STAT_TYPES: type_combo.setCurrentText(type_str)
        value_edit = QLineEdit(value_str); remove_btn = QPushButton("X"); remove_btn.setFixedSize(25, 25); line_layout.addWidget(type_combo, 1); line_layout.addWidget(QLabel(" 값:")); line_layout.addWidget(value_edit, 1); line_layout.addWidget(remove_btn); widget_set = {"layout": line_layout, "type": type_combo, "value": value_edit, "button": remove_btn}; self.effect_widgets.append(widget_set); remove_btn.clicked.connect(lambda: self.remove_line(widget_set, self.effect_widgets, self.effects_layout)); self.effects_layout.addLayout(line_layout)
    def add_param_line(self, text=""):
        line_layout = QHBoxLayout(); line_edit = QLineEdit(text); remove_btn = QPushButton("X"); remove_btn.setFixedSize(25, 25); line_layout.addWidget(line_edit, 1); line_layout.addWidget(remove_btn); widget_set = {"layout": line_layout, "input": line_edit, "button": remove_btn}; self.param_widgets.append(widget_set); remove_btn.clicked.connect(lambda: self.remove_line(widget_set, self.param_widgets, self.params_layout)); self.params_layout.addLayout(line_layout)
    def remove_line(self, widget_set, widget_list, layout):
        for i in reversed(range(widget_set["layout"].count())): 
            widget = widget_set["layout"].itemAt(i).widget()
            if widget: widget.deleteLater()
        layout.removeItem(widget_set["layout"]); widget_list.remove(widget_set)
    def get_data(self):
        effects = []
        for ws in self.effect_widgets:
            try: effects.append({"type": ws["type"].currentText(), "value": float(ws["value"].text().strip())})
            except ValueError: print(f"경고: 스탯 값 '{ws['value'].text()}' 무시됨.")
        params = [ws["input"].text().strip() for ws in self.param_widgets if ws["input"].text().strip()]
        return {'name': self.inputs['name'].text().strip(), 'effects': effects, 'params': params}
class CharacterDialog(QDialog):
    def __init__(self, title, defaults=None, parent=None):
        super().__init__(parent); self.setWindowTitle(title); layout = QFormLayout(self); self.inputs = {}; self.inputs['name'] = QLineEdit(defaults.get('name', '') if defaults else ''); layout.addRow(QLabel("이름:"), self.inputs['name']); self.inputs['attribute'] = QComboBox(); self.inputs['attribute'].addItems(ATTRIBUTES);
        if defaults and defaults.get('attribute') in ATTRIBUTES: self.inputs['attribute'].setCurrentText(defaults.get('attribute'))
        layout.addRow(QLabel("속성:"), self.inputs['attribute']); self.inputs['rarity'] = QComboBox(); self.inputs['rarity'].addItems(RARITIES);
        if defaults and defaults.get('rarity') in RARITIES: self.inputs['rarity'].setCurrentText(defaults.get('rarity'))
        layout.addRow(QLabel("성급:"), self.inputs['rarity']); button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel); button_box.accepted.connect(self.accept); button_box.rejected.connect(self.reject); layout.addWidget(button_box)
    def get_data(self): return {'name': self.inputs['name'].text().strip(), 'attribute': self.inputs['attribute'].currentText(), 'rarity': self.inputs['rarity'].currentText()}
class InputDialog(QDialog):
    def __init__(self, title, fields, defaults=None, parent=None):
        super().__init__(parent); self.setWindowTitle(title); layout = QFormLayout(self); self.inputs = {}
        for i, field in enumerate(fields): default_text = defaults[i] if defaults and len(defaults) > i else ""; self.inputs[field] = QLineEdit(default_text); layout.addRow(QLabel(f"{field}:"), self.inputs[field])
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel); button_box.accepted.connect(self.accept); button_box.rejected.connect(self.reject); layout.addWidget(button_box)
    def get_data(self):
        data = {};
        for field, line_edit in self.inputs.items(): data[field] = line_edit.text().strip()
        return data

# --- 메인 편집기 창 ---
class DBEditorApp(QWidget):
    # ... (이전과 동일)
    STYLE_ICON_DEFAULT = "font-size: 10px; background-color: #f0f0f0; border: 1px dashed #aaa; text-align: bottom; padding-bottom: 5px;"
    STYLE_ICON_SELECTED = "font-size: 10px; background-color: #d0e7ff; border: 2px solid #007bff; text-align: bottom; padding-bottom: 5px;"
    def __init__(self):
        super().__init__(); self.data_parser = DataParser(); self.game_data = {}; self.user_decks = {}; self.character_map = {}; self.current_char_filter = None; self.char_filter_buttons = []; self.potential_add_buttons = {}; self.initUI(); self.load_all_data()

    # (★수정★) on_character_selected 함수만 수정
    def on_character_selected(self, current_item, previous_item=None):
        for key, _ in STYLE_TYPES:
            if hasattr(self, f"potential_list_{key}"): getattr(self, f"potential_list_{key}").clear()
        if not current_item: self.potential_tabs.setEnabled(False); return
        self.potential_tabs.setEnabled(True); char_data = current_item.data(Qt.ItemDataRole.UserRole)
        char_id = char_data.get("id")
        if not char_id: return
        
        for pot in self.game_data.get("potentials", []):
            if pot.get("character_id") == char_id:
                style_key = pot.get("style_type")
                if style_key and hasattr(self, f"potential_list_{style_key}"):
                    list_widget = getattr(self, f"potential_list_{style_key}")
                    list_item = QListWidgetItem(pot.get("name", "이름없음"))
                    
                    tooltip_parts = []
                    # 1. 사용자 직접 입력 효과 (effects)
                    effects_text = "\n".join([f"- {e['type']}: {e['value']}" for e in pot.get('effects', [])])
                    if effects_text: tooltip_parts.append(f"입력된 효과:\n{effects_text}")
                    
                    # 2. Param 파싱 효과
                    parsed_effects = []
                    for param in pot.get('params', []):
                        parsed = self.data_parser.parse_param(param)
                        if parsed: parsed_effects.append(f"- {parsed['type']}: {parsed['value']:.1f}")
                    if parsed_effects: tooltip_parts.append("파싱된 효과:\n" + "\n".join(parsed_effects))
                    
                    list_item.setToolTip("\n\n".join(tooltip_parts))
                    
                    list_item.setData(Qt.ItemDataRole.UserRole, pot)
                    list_widget.addItem(list_item)
    
    # --- (이하 모든 함수는 변경 없음) ---
    def initUI(self):
        self.setWindowTitle("스텔라 소라 DB 편집기 (v2.14.2)"); self.setGeometry(100, 100, 1000, 700); main_layout = QVBoxLayout(); self.tabs = QTabWidget(); self.tabs.addTab(self.create_userdecks_tab(), "내 덱 (user_decks.json)"); self.tabs.addTab(self.create_gamedata_tab(), "게임 데이터 (gamedata.json)"); self.tabs.setCurrentIndex(0); main_layout.addWidget(self.tabs); self.save_button = QPushButton("모든 변경사항 저장"); self.save_button.setStyleSheet("font-size: 16px; padding: 10px; background-color: #007bff; color: white;"); self.save_button.clicked.connect(self.save_all_data); main_layout.addWidget(self.save_button); self.setLayout(main_layout); self._setup_shortcuts()
    def _setup_shortcuts(self): shortcut_add = QShortcut(QKeySequence("9"), self); shortcut_add.activated.connect(self.on_shortcut_add_potential)
    def on_shortcut_add_potential(self):
        if self.tabs.currentIndex() == 1: 
            current_potential_tab_index = self.potential_tabs.currentIndex()
            if current_potential_tab_index != -1:
                style_key = STYLE_TYPES[current_potential_tab_index][0]; add_button = self.potential_add_buttons.get(style_key)
                if add_button and add_button.isEnabled(): add_button.click()
    def create_gamedata_tab(self):
        widget = QWidget(); layout = QHBoxLayout(widget); main_splitter = QSplitter(Qt.Orientation.Horizontal); char_pot_splitter = QSplitter(Qt.Orientation.Horizontal); char_pot_splitter.addWidget(self.create_character_manager()); char_pot_splitter.addWidget(self.create_potential_manager()); main_splitter.addWidget(char_pot_splitter); sound_record_widget = QWidget(); sound_record_layout = QVBoxLayout(sound_record_widget); sound_record_layout.addWidget(self.create_list_manager_widget("sounds", "소리", ["name", "effect"])); sound_record_layout.addWidget(self.create_list_manager_widget("records", "레코드", ["name", "concerto_skill", "sounds_needed"])); main_splitter.addWidget(sound_record_widget); main_splitter.setSizes([700, 300]); layout.addWidget(main_splitter); return widget
    def create_character_manager(self):
        widget = QWidget(); layout = QVBoxLayout(widget); layout.addWidget(QLabel("--- 1. 캐릭터 목록 (속성/성급순 정렬) ---")); self.character_list = QListWidget(); self.character_list.currentItemChanged.connect(self.on_character_selected); layout.addWidget(self.character_list); button_layout = QHBoxLayout(); add_btn = QPushButton("캐릭터 추가"); edit_btn = QPushButton("정보 수정"); del_btn = QPushButton("캐릭터 삭제"); add_btn.clicked.connect(self.add_character); edit_btn.clicked.connect(self.edit_character); del_btn.clicked.connect(self.del_character); button_layout.addWidget(add_btn); button_layout.addWidget(edit_btn); button_layout.addWidget(del_btn); layout.addLayout(button_layout); return widget
    def create_potential_manager(self):
        widget = QWidget(); layout = QVBoxLayout(widget); layout.addWidget(QLabel("--- 2. 잠재력 목록 (선택된 캐릭터) ---")); self.potential_tabs = QTabWidget(); self.potential_tabs.setEnabled(False); self.potential_add_buttons = {} 
        for key, display_name in STYLE_TYPES: 
            tab_page = QWidget(); tab_layout = QVBoxLayout(tab_page); list_widget = QListWidget(); setattr(self, f"potential_list_{key}", list_widget); tab_layout.addWidget(list_widget); button_layout = QHBoxLayout(); 
            add_btn = QPushButton("잠재력 추가 (&A)"); self.potential_add_buttons[key] = add_btn; edit_btn = QPushButton("잠재력 수정 (&E)"); del_btn = QPushButton("잠재력 삭제 (&D)");
            add_btn.clicked.connect(lambda _, k=key: self.add_potential(k)); edit_btn.clicked.connect(lambda _, lw=list_widget: self.edit_potential(lw)); del_btn.clicked.connect(lambda _, lw=list_widget: self.del_potential(lw)); 
            button_layout.addWidget(add_btn); button_layout.addWidget(edit_btn); button_layout.addWidget(del_btn); tab_layout.addLayout(button_layout); self.potential_tabs.addTab(tab_page, display_name)
        layout.addWidget(self.potential_tabs); return widget
    def create_list_manager_widget(self, data_key, title, fields):
        widget = QWidget(); layout = QVBoxLayout(widget); layout.addWidget(QLabel(f"--- {title} 목록 ---")); list_widget = QListWidget(); setattr(self, f"{data_key}_list", list_widget); layout.addWidget(list_widget); button_layout = QHBoxLayout(); add_btn = QPushButton("추가"); edit_btn = QPushButton("수정"); del_btn = QPushButton("삭제"); add_btn.clicked.connect(lambda: self.add_gamedata_item(data_key, title, fields)); edit_btn.clicked.connect(lambda: self.edit_gamedata_item(data_key, title, fields)); del_btn.clicked.connect(lambda: self.del_gamedata_item(data_key)); button_layout.addWidget(add_btn); button_layout.addWidget(edit_btn); button_layout.addWidget(del_btn); layout.addLayout(button_layout); return widget
    def create_userdecks_tab(self):
        widget = QWidget(); layout = QVBoxLayout(widget); splitter = QSplitter(Qt.Orientation.Horizontal); deck_list_widget = QWidget(); deck_list_layout = QVBoxLayout(deck_list_widget); deck_list_layout.addWidget(QLabel("--- 내 덱 목록 ---")); self.decks_list = QListWidget(); self.decks_list.currentItemChanged.connect(self.on_deck_selected); deck_list_layout.addWidget(self.decks_list); deck_btn_layout = QHBoxLayout(); deck_add_btn = QPushButton("새 덱"); deck_del_btn = QPushButton("덱 삭제"); deck_add_btn.clicked.connect(self.add_deck); deck_del_btn.clicked.connect(self.del_deck); deck_btn_layout.addWidget(deck_add_btn); deck_btn_layout.addWidget(deck_del_btn); deck_list_layout.addLayout(deck_btn_layout); splitter.addWidget(deck_list_widget); deck_editor_widget = QWidget(); deck_editor_layout = QVBoxLayout(deck_editor_widget); self.deck_editor_label = QLabel("덱을 선택하세요"); self.deck_editor_label.setAlignment(Qt.AlignmentFlag.AlignCenter); self.deck_editor_label.setStyleSheet("font-size: 16px; font-weight: bold; margin-bottom: 5px;"); deck_editor_layout.addWidget(self.deck_editor_label); self.character_filter_bar = QScrollArea(); self.character_filter_bar.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff); self.character_filter_bar.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded); self.character_filter_bar.setFixedHeight(75); self.character_icon_container = QWidget(); self.character_icon_layout = QHBoxLayout(self.character_icon_container); self.character_icon_layout.setSpacing(10); self.character_icon_layout.setAlignment(Qt.AlignmentFlag.AlignLeft); self.character_filter_bar.setWidget(self.character_icon_container); self.character_filter_bar.setWidgetResizable(True); deck_editor_layout.addWidget(self.character_filter_bar); self.deck_editor_splitter = QSplitter(Qt.Orientation.Horizontal); all_pot_widget = QWidget(); all_pot_layout = QVBoxLayout(all_pot_widget); all_pot_layout.addWidget(QLabel("[전체 잠재력] (더블클릭/버튼으로 추가)")); self.all_potentials_list = QListWidget(); self.all_potentials_list.itemDoubleClicked.connect(self.add_potential_to_deck); all_pot_layout.addWidget(self.all_potentials_list); current_deck_widget = QWidget(); current_deck_layout = QVBoxLayout(current_deck_widget); current_deck_layout.addWidget(QLabel("[현재 덱 잠재력] (더블클릭/버튼으로 제거)")); self.current_deck_potentials_list = QListWidget(); self.current_deck_potentials_list.itemDoubleClicked.connect(self.remove_potential_from_deck); current_deck_layout.addWidget(self.current_deck_potentials_list); add_remove_btn_layout = QVBoxLayout(); add_to_deck_btn = QPushButton(">>"); add_to_deck_btn.clicked.connect(self.add_potential_to_deck); remove_from_deck_btn = QPushButton("<<"); remove_from_deck_btn.clicked.connect(self.remove_potential_from_deck); add_remove_btn_layout.addWidget(add_to_deck_btn); add_remove_btn_layout.addWidget(remove_from_deck_btn); btn_temp_widget = QWidget(); btn_temp_widget.setLayout(add_remove_btn_layout); btn_temp_widget.setFixedWidth(50); self.deck_editor_splitter.addWidget(all_pot_widget); self.deck_editor_splitter.addWidget(btn_temp_widget); self.deck_editor_splitter.addWidget(current_deck_widget); deck_editor_layout.addWidget(self.deck_editor_splitter); splitter.addWidget(deck_editor_widget); layout.addWidget(splitter); return widget
    def clear_layout(self, layout):
        if layout:
            while layout.count():
                item = layout.takeAt(0)
                if item.widget(): item.widget().deleteLater()
                elif item.layout(): self.clear_layout(item.layout())
    def load_all_data(self):
        try:
            if os.path.exists(GAMEDATA_FILE):
                with open(GAMEDATA_FILE, 'r', encoding='utf-8') as f: self.game_data = json.load(f)
            else: self.game_data = {"characters": [], "potentials": [], "sounds": [], "records": []}
            if os.path.exists(USERDECKS_FILE):
                with open(USERDECKS_FILE, 'r', encoding='utf-8') as f: self.user_decks = json.load(f)
            else: self.user_decks = {}
            self.refresh_character_list(); self.refresh_character_filter_bar(); self.refresh_sound_and_record_lists(); self.refresh_all_potentials_list_in_deck_tab(); self.refresh_deck_list()
        except Exception as e: QMessageBox.critical(self, "오류", f"데이터 파일 로드 실패: {e}")
    def add_potential(self, style_key):
        selected_char_item = self.character_list.currentItem()
        if not selected_char_item: QMessageBox.warning(self, "알림", "먼저 캐릭터를 선택하세요."); return
        char_data = selected_char_item.data(Qt.ItemDataRole.UserRole)
        dialog = PotentialDialog("새 잠재력 추가", parent=self)
        if dialog.exec():
            new_data = dialog.get_data()
            if not new_data.get('name'): QMessageBox.warning(self, "알림", "잠재력 이름을 입력해야 합니다."); return
            new_pot = {"id": f"p_{uuid.uuid4()}", "character_id": char_data["id"], "style_type": style_key, **new_data}
            self.game_data["potentials"].append(new_pot)
            self.on_character_selected(selected_char_item); self.refresh_all_potentials_list_in_deck_tab()
    def edit_potential(self, list_widget):
        selected_item = list_widget.currentItem()
        if not selected_item: QMessageBox.warning(self, "알림", "수정할 잠재력을 선택하세요."); return
        old_data = selected_item.data(Qt.ItemDataRole.UserRole)
        dialog = PotentialDialog("잠재력 정보 수정", old_data, self)
        if dialog.exec():
            new_data = dialog.get_data()
            if not new_data.get('name'): QMessageBox.warning(self, "알림", "이름을 비워둘 수 없습니다."); return
            for i, pot in enumerate(self.game_data["potentials"]):
                if pot.get("id") == old_data.get("id"):
                    self.game_data["potentials"][i].update(new_data); break
            self.on_character_selected(self.character_list.currentItem()); self.refresh_all_potentials_list_in_deck_tab()
    def del_potential(self, list_widget):
        selected_item = list_widget.currentItem()
        if not selected_item: return
        old_data = selected_item.data(Qt.ItemDataRole.UserRole); reply = QMessageBox.question(self, "삭제 확인", f"'{old_data.get('name')}' 잠재력을 정말 삭제하시겠습니까?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes: self.game_data["potentials"] = [p for p in self.game_data["potentials"] if p.get("id") != old_data.get("id")]; self.on_character_selected(self.character_list.currentItem()); self.refresh_all_potentials_list_in_deck_tab()
    def refresh_character_list(self):
        self.character_list.clear(); self.character_map = {}
        characters = sorted(self.game_data.get("characters", []), key=lambda c: (ATTRIBUTE_ORDER.get(c.get("attribute"), 99), 0 if c.get("rarity") == "5성" else 1, c.get("name", "")))
        for char in characters: list_item = QListWidgetItem(f"[{char.get('attribute', '?')}] [{char.get('rarity', '?')}] {char.get('name', '이름없음')}"); list_item.setData(Qt.ItemDataRole.UserRole, char); self.character_list.addItem(list_item); self.character_map[char.get("id")] = char.get("name", "이름없음")
    def add_character(self):
        dialog = CharacterDialog("새 캐릭터 추가", parent=self)
        if dialog.exec():
            new_data = dialog.get_data()
            if not new_data.get('name'): QMessageBox.warning(self, "알림", "캐릭터 이름을 입력해야 합니다."); return
            new_char = {"id": f"c_{uuid.uuid4()}", **new_data}; self.game_data["characters"].append(new_char); self.refresh_character_list(); self.refresh_all_potentials_list_in_deck_tab(); self.refresh_character_filter_bar()
    def edit_character(self):
        selected_item = self.character_list.currentItem()
        if not selected_item: return
        old_data = selected_item.data(Qt.ItemDataRole.UserRole); dialog = CharacterDialog("캐릭터 정보 수정", old_data, self)
        if dialog.exec():
            new_data = dialog.get_data()
            if not new_data.get('name'): QMessageBox.warning(self, "알림", "이름을 비워둘 수 없습니다."); return
            for i, char in enumerate(self.game_data["characters"]):
                if char["id"] == old_data["id"]: self.game_data["characters"][i] = {"id": old_data["id"], **new_data}; break
            self.refresh_character_list(); self.refresh_all_potentials_list_in_deck_tab(); self.refresh_character_filter_bar()
    def del_character(self):
        selected_item = self.character_list.currentItem()
        if not selected_item: return
        char_data = selected_item.data(Qt.ItemDataRole.UserRole); char_id = char_data["id"]; reply = QMessageBox.question(self, "삭제 확인", f"'{char_data['name']}' 캐릭터와 모든 잠재력을 삭제하시겠습니까?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.game_data["characters"] = [c for c in self.game_data["characters"] if c["id"] != char_id]; self.game_data["potentials"] = [p for p in self.game_data["potentials"] if p.get("character_id") != char_id]; self.refresh_character_list(); self.refresh_all_potentials_list_in_deck_tab(); self.refresh_character_filter_bar()
            if self.current_char_filter == char_id: self.on_character_filter_clicked(None)
    def refresh_sound_and_record_lists(self):
        self.sounds_list.clear(); self.records_list.clear()
        for item in self.game_data.get("sounds", []): list_item = QListWidgetItem(f"{item.get('name', '')} ({item.get('effect', '')})"); list_item.setData(Qt.ItemDataRole.UserRole, item); self.sounds_list.addItem(list_item)
        for item in self.game_data.get("records", []): list_item = QListWidgetItem(f"{item.get('name', '')} (필요소리: {item.get('sounds_needed', 0)})"); list_item.setData(Qt.ItemDataRole.UserRole, item); self.records_list.addItem(list_item)
    def add_gamedata_item(self, data_key, title, fields):
        dialog = InputDialog(f"{title} 추가", fields, parent=self)
        if dialog.exec(): new_data = dialog.get_data();
        if not new_data.get('name'): return
        new_data['id'] = f"{data_key[:1]}_{uuid.uuid4()}"; self.game_data[data_key].append(new_data); self.refresh_sound_and_record_lists()
    def edit_gamedata_item(self, data_key, title, fields):
        list_widget = getattr(self, f"{data_key}_list"); selected_item = list_widget.currentItem();
        if not selected_item: return
        old_data = selected_item.data(Qt.ItemDataRole.UserRole); defaults = [old_data.get(field, "") for field in fields]; dialog = InputDialog(f"{title} 수정", fields, defaults, self)
        if dialog.exec():
            new_data = dialog.get_data()
            if not new_data.get('name'): return
            for i, item in enumerate(self.game_data[data_key]):
                if item["id"] == old_data["id"]: new_data['id'] = item["id"]; self.game_data[data_key][i] = new_data; break
            self.refresh_sound_and_record_lists()
    def del_gamedata_item(self, data_key):
        list_widget = getattr(self, f"{data_key}_list"); selected_item = list_widget.currentItem()
        if not selected_item: return
        reply = QMessageBox.question(self, "삭제 확인", "정말 삭제하시겠습니까?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes: old_data = selected_item.data(Qt.ItemDataRole.UserRole); self.game_data[data_key] = [item for item in self.game_data[data_key] if item["id"] != old_data["id"]]; self.refresh_sound_and_record_lists()
    def refresh_deck_list(self): self.decks_list.clear(); self.decks_list.addItems(self.user_decks.keys())
    def refresh_character_filter_bar(self):
        self.clear_layout(self.character_icon_layout); self.char_filter_buttons.clear(); btn_all = QPushButton("전체"); btn_all.setFixedSize(50, 50); btn_all.setProperty("char_id", None); btn_all.clicked.connect(lambda: self.on_character_filter_clicked(None)); self.character_icon_layout.addWidget(btn_all); self.char_filter_buttons.append(btn_all)
        for char in self.game_data.get("characters", []): char_id = char.get("id"); char_name = char.get("name"); btn = QPushButton(char_name); btn.setFixedSize(50, 50); btn.setProperty("char_id", char_id); btn.clicked.connect(lambda _, c_id=char_id: self.on_character_filter_clicked(c_id)); self.character_icon_layout.addWidget(btn); self.char_filter_buttons.append(btn)
        self.update_filter_button_styles()
    def on_character_filter_clicked(self, char_id): self.current_char_filter = char_id; self.update_filter_button_styles(); self.refresh_all_potentials_list_in_deck_tab()
    def update_filter_button_styles(self): [btn.setStyleSheet(self.STYLE_ICON_SELECTED if btn.property("char_id") == self.current_char_filter else self.STYLE_ICON_DEFAULT) for btn in self.char_filter_buttons]
    def refresh_all_potentials_list_in_deck_tab(self):
        self.all_potentials_list.clear(); style_display_map = dict(STYLE_TYPES)
        for pot in self.game_data.get("potentials", []):
            if self.current_char_filter is not None and pot.get("character_id") != self.current_char_filter: continue
            char_name = self.character_map.get(pot.get("character_id"), "???"); style_display_name = style_display_map.get(pot.get("style_type"), "기타"); display_text = f"[{char_name}] [{style_display_name}] {pot.get('name')}"; list_item = QListWidgetItem(display_text); list_item.setData(Qt.ItemDataRole.UserRole, display_text); self.all_potentials_list.addItem(list_item)
    def add_deck(self):
        dialog = InputDialog("새 덱 생성", ["name"], parent=self)
        if dialog.exec():
            deck_name = dialog.get_data().get('name')
            if not deck_name: return
            if deck_name in self.user_decks: QMessageBox.warning(self, "알림", "이미 존재하는 덱 이름입니다."); return
            self.user_decks[deck_name] = {"name": deck_name, "potentials": []}; self.refresh_deck_list(); items = self.decks_list.findItems(deck_name, Qt.MatchFlag.MatchExactly)
            if items: self.decks_list.setCurrentItem(items[0])
    def del_deck(self):
        selected_item = self.decks_list.currentItem()
        if not selected_item: return
        deck_name = selected_item.text(); reply = QMessageBox.question(self, "삭제 확인", f"'{deck_name}' 덱을 정말 삭제하시겠습니까?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            if deck_name in self.user_decks: del self.user_decks[deck_name]
            self.refresh_deck_list(); self.on_deck_selected(None)
    def on_deck_selected(self, current_item, previous_item=None):
        self.current_deck_potentials_list.clear()
        if not current_item: self.deck_editor_label.setText("덱을 선택하세요"); self.on_character_filter_clicked(None); return
        deck_name = current_item.text(); self.deck_editor_label.setText(f"--- [{deck_name}] 편집 중 ---"); deck_data = self.user_decks.get(deck_name)
        if deck_data: self.current_deck_potentials_list.addItems(deck_data.get("potentials", []))
    def add_potential_to_deck(self):
        selected_deck_item = self.decks_list.currentItem(); selected_potential_item = self.all_potentials_list.currentItem()
        if not (selected_deck_item and selected_potential_item): return
        deck_name = selected_deck_item.text(); display_text = selected_potential_item.data(Qt.ItemDataRole.UserRole); deck_potentials = self.user_decks[deck_name]["potentials"]
        if display_text in deck_potentials: return
        deck_potentials.append(display_text); self.current_deck_potentials_list.addItem(QListWidgetItem(display_text))
    def remove_potential_from_deck(self):
        selected_deck_item = self.decks_list.currentItem(); selected_deck_potential_item = self.current_deck_potentials_list.currentItem()
        if not (selected_deck_item and selected_deck_potential_item): return
        deck_name = selected_deck_item.text(); display_text = selected_deck_potential_item.text()
        if display_text in self.user_decks[deck_name]["potentials"]: self.user_decks[deck_name]["potentials"].remove(display_text)
        self.current_deck_potentials_list.takeItem(self.current_deck_potentials_list.row(selected_deck_potential_item))
    def save_all_data(self):
        try:
            with open(GAMEDATA_FILE, 'w', encoding='utf-8') as f: json.dump(self.game_data, f, indent=2, ensure_ascii=False)
            with open(USERDECKS_FILE, 'w', encoding='utf-8') as f: json.dump(self.user_decks, f, indent=2, ensure_ascii=False)
            QMessageBox.information(self, "성공", f"{GAMEDATA_FILE} 와 {USERDECKS_FILE} 파일이 저장되었습니다.")
        except Exception as e: QMessageBox.critical(self, "오류", f"파일 저장 실패: {e}")

if __name__ == '__main__':
    app = QApplication(sys.argv); ex = DBEditorApp(); ex.show(); sys.exit(app.exec())