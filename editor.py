# editor.py (v2.12 - 잠재력 추가 단축키 '9' 추가)
import sys
import json
import os
import uuid
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
                             QPushButton, QLabel, QListWidget, QListWidgetItem,
                             QLineEdit, QTabWidget, QSplitter, QMessageBox,
                             QFormLayout, QDialog, QDialogButtonBox, QScrollArea,
                             QComboBox)
# (수정) QShortcut 추가
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QShortcut, QKeySequence # QShortcut, QKeySequence 추가

# --- 경로 설정 함수 ---
# (v2.11과 동일)
def get_datafile_path(relative_path):
    if getattr(sys, 'frozen', False): base_path = os.path.dirname(sys.executable)
    else: base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)
# --------------------

# --- 설정 파일 정의 ---
# (v2.11과 동일)
GAMEDATA_FILE = get_datafile_path('gamedata.json')
USERDECKS_FILE = get_datafile_path('user_decks.json')

# --- 상수 정의 ---
# (v2.11과 동일)
STYLE_TYPES = [("main1", "메인유파1"), ("main2", "메인유파2"), ("main_common", "메인공용"), ("support1", "지원유파1"), ("support2", "지원유파2"), ("support_common", "지원공용")]
ATTRIBUTES = ["빛", "어둠", "땅", "불", "물", "바람"]
RARITIES = ["5성", "4성"]
ATTRIBUTE_ORDER = {"빛": 0, "어둠": 1, "땅": 2, "불": 3, "물": 4, "바람": 5}
# ----------------------

# --- 캐릭터 추가/수정용 팝업 ---
# (CharacterDialog 클래스 코드는 v2.11과 동일)
class CharacterDialog(QDialog):
    def __init__(self, title, defaults=None, parent=None):
        super().__init__(parent); self.setWindowTitle(title); layout = QFormLayout(self); self.inputs = {}; self.inputs['name'] = QLineEdit(defaults.get('name', '') if defaults else ''); layout.addRow(QLabel("이름:"), self.inputs['name']); self.inputs['attribute'] = QComboBox(); self.inputs['attribute'].addItems(ATTRIBUTES);
        if defaults and defaults.get('attribute') in ATTRIBUTES: self.inputs['attribute'].setCurrentText(defaults.get('attribute'))
        layout.addRow(QLabel("속성:"), self.inputs['attribute']); self.inputs['rarity'] = QComboBox(); self.inputs['rarity'].addItems(RARITIES);
        if defaults and defaults.get('rarity') in RARITIES: self.inputs['rarity'].setCurrentText(defaults.get('rarity'))
        layout.addRow(QLabel("성급:"), self.inputs['rarity']); button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel); button_box.accepted.connect(self.accept); button_box.rejected.connect(self.reject); layout.addWidget(button_box)
    def get_data(self): return {'name': self.inputs['name'].text().strip(), 'attribute': self.inputs['attribute'].currentText(), 'rarity': self.inputs['rarity'].currentText()}

# --- 잠재력/소리/레코드용 팝업 ---
# (InputDialog 클래스 코드는 v2.11과 동일)
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
    # (v2.11과 동일한 스타일)
    STYLE_ICON_DEFAULT = "font-size: 10px; background-color: #f0f0f0; border: 1px dashed #aaa; text-align: bottom; padding-bottom: 5px;"
    STYLE_ICON_SELECTED = "font-size: 10px; background-color: #d0e7ff; border: 2px solid #007bff; text-align: bottom; padding-bottom: 5px;"
    def __init__(self):
        super().__init__(); self.game_data = {}; self.user_decks = {}; self.character_map = {}; self.current_char_filter = None; self.char_filter_buttons = [];
        # (신규) 잠재력 추가 버튼 참조 저장용 딕셔너리
        self.potential_add_buttons = {}
        self.initUI(); self.load_all_data()

    def initUI(self):
        # (v2.11과 동일)
        self.setWindowTitle("스텔라 소라 DB 편집기 (v2.12 - 단축키 추가)"); self.setGeometry(100, 100, 1000, 700); main_layout = QVBoxLayout(); self.tabs = QTabWidget(); self.tabs.addTab(self.create_userdecks_tab(), "내 덱 (user_decks.json)"); self.tabs.addTab(self.create_gamedata_tab(), "게임 데이터 (gamedata.json)"); self.tabs.setCurrentIndex(0); main_layout.addWidget(self.tabs); self.save_button = QPushButton("모든 변경사항 저장"); self.save_button.setStyleSheet("font-size: 16px; padding: 10px; background-color: #007bff; color: white;"); self.save_button.clicked.connect(self.save_all_data); main_layout.addWidget(self.save_button); self.setLayout(main_layout)
        # (신규) 단축키 연결
        self._setup_shortcuts()

    # --- (신규) 단축키 설정 함수 ---
    def _setup_shortcuts(self):
        # '9' 키를 눌렀을 때 on_shortcut_add_potential 함수 실행
        shortcut_add = QShortcut(QKeySequence("9"), self)
        shortcut_add.activated.connect(self.on_shortcut_add_potential)
    # ----------------------------

    # --- (신규) 단축키 실행 함수 ---
    def on_shortcut_add_potential(self):
        """'9' 단축키가 눌렸을 때 실행될 함수"""
        # 1. 현재 활성화된 탭 확인 (게임 데이터 탭인지?)
        if self.tabs.currentIndex() == 1: # 0: 내 덱, 1: 게임 데이터
            # 2. 게임 데이터 탭 내에서 활성화된 잠재력 유파 탭 확인
            current_potential_tab_index = self.potential_tabs.currentIndex()
            if current_potential_tab_index != -1: # 유효한 탭이 선택되어 있다면
                # 3. 해당 탭의 유파 키(key) 찾기 (예: "main1")
                style_key = STYLE_TYPES[current_potential_tab_index][0]
                # 4. 해당 유파의 '잠재력 추가' 버튼 찾기
                add_button = self.potential_add_buttons.get(style_key)
                if add_button and add_button.isEnabled():
                    # 5. 버튼 클릭 시뮬레이션
                    print(f"단축키 '9': '{STYLE_TYPES[current_potential_tab_index][1]}' 잠재력 추가 버튼 클릭됨")
                    add_button.click()
                else:
                    print(f"단축키 '9': '{STYLE_TYPES[current_potential_tab_index][1]}' 잠재력 추가 버튼 비활성화됨 (캐릭터 선택 필요?)")
            else:
                 print("단축키 '9': 활성화된 잠재력 탭 없음")
        else:
            print("단축키 '9': 게임 데이터 탭이 활성화되지 않음")
    # ----------------------------

    def create_gamedata_tab(self):
        # (v2.11과 동일)
        widget = QWidget(); layout = QHBoxLayout(widget); main_splitter = QSplitter(Qt.Orientation.Horizontal); char_pot_splitter = QSplitter(Qt.Orientation.Horizontal); char_pot_splitter.addWidget(self.create_character_manager()); char_pot_splitter.addWidget(self.create_potential_manager()); main_splitter.addWidget(char_pot_splitter); sound_record_widget = QWidget(); sound_record_layout = QVBoxLayout(sound_record_widget); sound_record_layout.addWidget(self.create_list_manager_widget("sounds", "소리", ["name", "effect"])); sound_record_layout.addWidget(self.create_list_manager_widget("records", "레코드", ["name", "concerto_skill", "sounds_needed"])); main_splitter.addWidget(sound_record_widget); main_splitter.setSizes([700, 300]); layout.addWidget(main_splitter); return widget
    def create_character_manager(self):
        # (v2.11과 동일)
        widget = QWidget(); layout = QVBoxLayout(widget); layout.addWidget(QLabel("--- 1. 캐릭터 목록 (속성/성급순 정렬) ---")); self.character_list = QListWidget(); self.character_list.currentItemChanged.connect(self.on_character_selected); layout.addWidget(self.character_list); button_layout = QHBoxLayout(); add_btn = QPushButton("캐릭터 추가"); edit_btn = QPushButton("정보 수정"); del_btn = QPushButton("캐릭터 삭제"); add_btn.clicked.connect(self.add_character); edit_btn.clicked.connect(self.edit_character); del_btn.clicked.connect(self.del_character); button_layout.addWidget(add_btn); button_layout.addWidget(edit_btn); button_layout.addWidget(del_btn); layout.addLayout(button_layout); return widget
    
    # --- (★수정된 부분★) ---
    def create_potential_manager(self):
        widget = QWidget(); layout = QVBoxLayout(widget); layout.addWidget(QLabel("--- 2. 잠재력 목록 (선택된 캐릭터) ---")); self.potential_tabs = QTabWidget(); self.potential_tabs.setEnabled(False)
        # self.potential_add_buttons 딕셔너리 초기화
        self.potential_add_buttons = {} 
        
        for key, display_name in STYLE_TYPES: 
            tab_page = QWidget(); tab_layout = QVBoxLayout(tab_page); list_widget = QListWidget(); setattr(self, f"potential_list_{key}", list_widget); tab_layout.addWidget(list_widget); button_layout = QHBoxLayout(); 
            
            # '잠재력 추가' 버튼에 변수 할당
            add_btn = QPushButton("잠재력 추가 (&A)") # (&A): Alt+A 단축키 (선택사항)
            # 딕셔너리에 버튼 참조 저장
            self.potential_add_buttons[key] = add_btn 
            
            edit_btn = QPushButton("이름 수정 (&E)"); # (&E): Alt+E
            del_btn = QPushButton("잠재력 삭제 (&D)"); # (&D): Alt+D
            
            add_btn.clicked.connect(lambda _, k=key: self.add_potential(k)); 
            edit_btn.clicked.connect(lambda _, lw=list_widget: self.edit_potential(lw)); 
            del_btn.clicked.connect(lambda _, lw=list_widget: self.del_potential(lw)); 
            
            button_layout.addWidget(add_btn); button_layout.addWidget(edit_btn); button_layout.addWidget(del_btn); 
            tab_layout.addLayout(button_layout); 
            self.potential_tabs.addTab(tab_page, display_name)
            
        layout.addWidget(self.potential_tabs); return widget
    # ------------------------

    def create_list_manager_widget(self, data_key, title, fields):
        # (v2.11과 동일)
        widget = QWidget(); layout = QVBoxLayout(widget); layout.addWidget(QLabel(f"--- {title} 목록 ---")); list_widget = QListWidget(); setattr(self, f"{data_key}_list", list_widget); layout.addWidget(list_widget); button_layout = QHBoxLayout(); add_btn = QPushButton("추가"); edit_btn = QPushButton("수정"); del_btn = QPushButton("삭제"); add_btn.clicked.connect(lambda: self.add_gamedata_item(data_key, title, fields)); edit_btn.clicked.connect(lambda: self.edit_gamedata_item(data_key, title, fields)); del_btn.clicked.connect(lambda: self.del_gamedata_item(data_key)); button_layout.addWidget(add_btn); button_layout.addWidget(edit_btn); button_layout.addWidget(del_btn); layout.addLayout(button_layout); return widget
    def create_userdecks_tab(self):
        # (v2.11과 동일)
        widget = QWidget(); layout = QVBoxLayout(widget); splitter = QSplitter(Qt.Orientation.Horizontal); deck_list_widget = QWidget(); deck_list_layout = QVBoxLayout(deck_list_widget); deck_list_layout.addWidget(QLabel("--- 내 덱 목록 ---")); self.decks_list = QListWidget(); self.decks_list.currentItemChanged.connect(self.on_deck_selected); deck_list_layout.addWidget(self.decks_list); deck_btn_layout = QHBoxLayout(); deck_add_btn = QPushButton("새 덱"); deck_del_btn = QPushButton("덱 삭제"); deck_add_btn.clicked.connect(self.add_deck); deck_del_btn.clicked.connect(self.del_deck); deck_btn_layout.addWidget(deck_add_btn); deck_btn_layout.addWidget(deck_del_btn); deck_list_layout.addLayout(deck_btn_layout); splitter.addWidget(deck_list_widget); deck_editor_widget = QWidget(); deck_editor_layout = QVBoxLayout(deck_editor_widget); self.deck_editor_label = QLabel("덱을 선택하세요"); self.deck_editor_label.setAlignment(Qt.AlignmentFlag.AlignCenter); self.deck_editor_label.setStyleSheet("font-size: 16px; font-weight: bold; margin-bottom: 5px;"); deck_editor_layout.addWidget(self.deck_editor_label); self.character_filter_bar = QScrollArea(); self.character_filter_bar.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff); self.character_filter_bar.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded); self.character_filter_bar.setFixedHeight(75); self.character_icon_container = QWidget(); self.character_icon_layout = QHBoxLayout(self.character_icon_container); self.character_icon_layout.setSpacing(10); self.character_icon_layout.setAlignment(Qt.AlignmentFlag.AlignLeft); self.character_filter_bar.setWidget(self.character_icon_container); self.character_filter_bar.setWidgetResizable(True); deck_editor_layout.addWidget(self.character_filter_bar); self.deck_editor_splitter = QSplitter(Qt.Orientation.Horizontal); all_pot_widget = QWidget(); all_pot_layout = QVBoxLayout(all_pot_widget); all_pot_layout.addWidget(QLabel("[전체 잠재력] (더블클릭/버튼으로 추가)")); self.all_potentials_list = QListWidget(); self.all_potentials_list.itemDoubleClicked.connect(self.add_potential_to_deck); all_pot_layout.addWidget(self.all_potentials_list); current_deck_widget = QWidget(); current_deck_layout = QVBoxLayout(current_deck_widget); current_deck_layout.addWidget(QLabel("[현재 덱 잠재력] (더블클릭/버튼으로 제거)")); self.current_deck_potentials_list = QListWidget(); self.current_deck_potentials_list.itemDoubleClicked.connect(self.remove_potential_from_deck); current_deck_layout.addWidget(self.current_deck_potentials_list); add_remove_btn_layout = QVBoxLayout(); add_to_deck_btn = QPushButton(">>"); add_to_deck_btn.clicked.connect(self.add_potential_to_deck); remove_from_deck_btn = QPushButton("<<"); remove_from_deck_btn.clicked.connect(self.remove_potential_from_deck); add_remove_btn_layout.addWidget(add_to_deck_btn); add_remove_btn_layout.addWidget(remove_from_deck_btn); btn_temp_widget = QWidget(); btn_temp_widget.setLayout(add_remove_btn_layout); btn_temp_widget.setFixedWidth(50); self.deck_editor_splitter.addWidget(all_pot_widget); self.deck_editor_splitter.addWidget(btn_temp_widget); self.deck_editor_splitter.addWidget(current_deck_widget); deck_editor_layout.addWidget(self.deck_editor_splitter); splitter.addWidget(deck_editor_widget); layout.addWidget(splitter); return widget
    def clear_layout(self, layout):
        # (v2.11과 동일)
        if layout is None: return
        while layout.count():
            item = layout.takeAt(0)
            if item is None: continue
            widget = item.widget()
            if widget is not None: widget.deleteLater()
            else:
                sub_layout = item.layout()
                if sub_layout is not None: self.clear_layout(sub_layout)
    def load_all_data(self):
        # (v2.11과 동일)
        try:
            if os.path.exists(GAMEDATA_FILE):
                with open(GAMEDATA_FILE, 'r', encoding='utf-8') as f: self.game_data = json.load(f);
                if not isinstance(self.game_data, dict): self.game_data = {}
            else: self.game_data = {}
            if "characters" not in self.game_data: self.game_data["characters"] = []
            if "potentials" not in self.game_data: self.game_data["potentials"] = []
            if "sounds" not in self.game_data: self.game_data["sounds"] = []
            if "records" not in self.game_data: self.game_data["records"] = []
            if os.path.exists(USERDECKS_FILE):
                with open(USERDECKS_FILE, 'r', encoding='utf-8') as f: self.user_decks = json.load(f)
            else: self.user_decks = {}
            self.refresh_character_list(); self.refresh_character_filter_bar(); self.refresh_sound_and_record_lists(); self.refresh_all_potentials_list_in_deck_tab(); self.refresh_deck_list()
        except Exception as e: QMessageBox.critical(self, "오류", f"데이터 파일 로드 실패: {e}")

    # --- 이하 모든 함수는 v2.11과 동일 ---
    def refresh_character_list(self):
        self.character_list.clear(); self.character_map = {}
        characters = self.game_data.get("characters", [])
        def sort_key(char): attr = char.get("attribute", ""); rarity = char.get("rarity", ""); name = char.get("name", ""); attr_order = ATTRIBUTE_ORDER.get(attr, 99); rarity_order = 0 if rarity == "5성" else (1 if rarity == "4성" else 99); return (attr_order, rarity_order, name)
        sorted_characters = sorted(characters, key=sort_key)
        for char in sorted_characters: display_text = f"[{char.get('attribute', '?')}] [{char.get('rarity', '?')}] {char.get('name', '이름없음')}"; list_item = QListWidgetItem(display_text); list_item.setData(Qt.ItemDataRole.UserRole, char); self.character_list.addItem(list_item); self.character_map[char.get("id")] = char.get("name", "이름없음")
    def add_character(self):
        dialog = CharacterDialog("새 캐릭터 추가", parent=self);
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_data = dialog.get_data();
            if not new_data.get('name'): QMessageBox.warning(self, "알림", "캐릭터 이름을 입력해야 합니다."); return
            new_char = {"id": f"c_{uuid.uuid4()}", "name": new_data.get('name'), "attribute": new_data.get('attribute'), "rarity": new_data.get('rarity')}; self.game_data["characters"].append(new_char); self.refresh_character_list(); self.refresh_all_potentials_list_in_deck_tab(); self.refresh_character_filter_bar()
    def edit_character(self):
        selected_item = self.character_list.currentItem();
        if not selected_item: QMessageBox.warning(self, "알림", "수정할 캐릭터를 선택하세요."); return
        old_data = selected_item.data(Qt.ItemDataRole.UserRole); dialog = CharacterDialog("캐릭터 정보 수정", old_data, self);
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_data = dialog.get_data();
            if not new_data.get('name'): QMessageBox.warning(self, "알림", "이름을 비워둘 수 없습니다."); return
            for i, char in enumerate(self.game_data["characters"]):
                if char["id"] == old_data["id"]: self.game_data["characters"][i] = {"id": old_data["id"], "name": new_data.get("name"), "attribute": new_data.get("attribute"), "rarity": new_data.get("rarity")}; break
            self.refresh_character_list(); self.refresh_all_potentials_list_in_deck_tab(); self.refresh_character_filter_bar()
    def del_character(self):
        selected_item = self.character_list.currentItem();
        if not selected_item: return
        char_data = selected_item.data(Qt.ItemDataRole.UserRole); char_id = char_data["id"]; char_name = char_data["name"]; reply = QMessageBox.question(self, "삭제 확인", f"'{char_name}' 캐릭터를 정말 삭제하시겠습니까?\n이 캐릭터에 연결된 모든 잠재력도 함께 삭제됩니다!", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No);
        if reply == QMessageBox.StandardButton.Yes: self.game_data["characters"] = [c for c in self.game_data["characters"] if c["id"] != char_id]; self.game_data["potentials"] = [p for p in self.game_data["potentials"] if p.get("character_id") != char_id]; self.refresh_character_list(); self.refresh_all_potentials_list_in_deck_tab(); self.refresh_character_filter_bar();
        if self.current_char_filter == char_id: self.on_character_filter_clicked(None)
    def on_character_selected(self, current_item, previous_item=None):
        for key, _ in STYLE_TYPES:
            if hasattr(self, f"potential_list_{key}"): list_widget = getattr(self, f"potential_list_{key}"); list_widget.clear()
        if not current_item: self.potential_tabs.setEnabled(False); return
        self.potential_tabs.setEnabled(True); char_data = current_item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(char_data, dict) or "id" not in char_data: print("경고: 선택된 캐릭터 데이터 오류"); return
        char_id = char_data["id"]
        for pot in self.game_data.get("potentials", []):
            if not isinstance(pot, dict) or "character_id" not in pot: continue
            if pot.get("character_id") == char_id:
                style_key = pot.get("style_type")
                if style_key is not None and hasattr(self, f"potential_list_{style_key}"): list_widget = getattr(self, f"potential_list_{style_key}"); name = pot.get("name", "이름없음"); list_item = QListWidgetItem(name); list_item.setData(Qt.ItemDataRole.UserRole, pot); list_widget.addItem(list_item)
    def add_potential(self, style_key):
        selected_char_item = self.character_list.currentItem();
        if not selected_char_item: QMessageBox.warning(self, "알림", "먼저 왼쪽에서 캐릭터를 선택하세요."); return
        char_data = selected_char_item.data(Qt.ItemDataRole.UserRole); char_id = char_data["id"]; dialog = InputDialog("새 잠재력 추가", ["name"], parent=self);
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_data = dialog.get_data();
            if not new_data.get('name'): QMessageBox.warning(self, "알림", "잠재력 이름을 입력해야 합니다."); return
            new_pot = {"id": f"p_{uuid.uuid4()}", "character_id": char_id, "style_type": style_key, "name": new_data.get("name")}; self.game_data["potentials"].append(new_pot); self.on_character_selected(selected_char_item); self.refresh_all_potentials_list_in_deck_tab()
    def edit_potential(self, list_widget):
        selected_item = list_widget.currentItem();
        if not selected_item: QMessageBox.warning(self, "알림", "수정할 잠재력을 선택하세요."); return
        old_data = selected_item.data(Qt.ItemDataRole.UserRole); dialog = InputDialog("잠재력 이름 수정", ["name"], [old_data.get("name")], self);
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_data = dialog.get_data();
            if not new_data.get('name'): QMessageBox.warning(self, "알림", "이름을 비워둘 수 없습니다."); return
            for pot in self.game_data["potentials"]:
                if pot["id"] == old_data["id"]: pot["name"] = new_data["name"]; break
            self.on_character_selected(self.character_list.currentItem()); self.refresh_all_potentials_list_in_deck_tab()
    def del_potential(self, list_widget):
        selected_item = list_widget.currentItem();
        if not selected_item: QMessageBox.warning(self, "알림", "삭제할 잠재력을 선택하세요."); return
        old_data = selected_item.data(Qt.ItemDataRole.UserRole); reply = QMessageBox.question(self, "삭제 확인", f"'{old_data.get('name')}' 잠재력을 정말 삭제하시겠습니까?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No);
        if reply == QMessageBox.StandardButton.Yes: self.game_data["potentials"] = [p for p in self.game_data["potentials"] if p["id"] != old_data["id"]]; self.on_character_selected(self.character_list.currentItem()); self.refresh_all_potentials_list_in_deck_tab()
    def refresh_sound_and_record_lists(self):
        self.sounds_list.clear();
        for item in self.game_data.get("sounds", []): list_item = QListWidgetItem(f"{item.get('name', '')} ({item.get('effect', '')})"); list_item.setData(Qt.ItemDataRole.UserRole, item); self.sounds_list.addItem(list_item)
        self.records_list.clear();
        for item in self.game_data.get("records", []): list_item = QListWidgetItem(f"{item.get('name', '')} (필요소리: {item.get('sounds_needed', 0)})"); list_item.setData(Qt.ItemDataRole.UserRole, item); self.records_list.addItem(list_item)
    def add_gamedata_item(self, data_key, title, fields):
        dialog = InputDialog(f"{title} 추가", fields, parent=self);
        if dialog.exec() == QDialog.DialogCode.Accepted: new_data = dialog.get_data();
        if not new_data.get('name'): return
        new_data['id'] = f"{data_key[:1]}_{uuid.uuid4()}"; self.game_data[data_key].append(new_data); self.refresh_sound_and_record_lists()
    def edit_gamedata_item(self, data_key, title, fields):
        list_widget = getattr(self, f"{data_key}_list"); selected_item = list_widget.currentItem();
        if not selected_item: return
        old_data = selected_item.data(Qt.ItemDataRole.UserRole); defaults = [old_data.get(field, "") for field in fields]; dialog = InputDialog(f"{title} 수정", fields, defaults, self);
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_data = dialog.get_data();
            if not new_data.get('name'): return
            for i, item in enumerate(self.game_data[data_key]):
                if item["id"] == old_data["id"]: new_data['id'] = item["id"]; self.game_data[data_key][i] = new_data; break
            self.refresh_sound_and_record_lists()
    def del_gamedata_item(self, data_key):
        list_widget = getattr(self, f"{data_key}_list"); selected_item = list_widget.currentItem();
        if not selected_item: return
        reply = QMessageBox.question(self, "삭제 확인", "정말 삭제하시겠습니까?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No);
        if reply == QMessageBox.StandardButton.Yes: old_data = selected_item.data(Qt.ItemDataRole.UserRole); self.game_data[data_key] = [item for item in self.game_data[data_key] if item["id"] != old_data["id"]]; self.refresh_sound_and_record_lists()
    def refresh_deck_list(self): self.decks_list.clear(); [self.decks_list.addItem(QListWidgetItem(deck_name)) for deck_name in self.user_decks.keys()]
    def refresh_character_filter_bar(self):
        self.clear_layout(self.character_icon_layout); self.char_filter_buttons.clear(); btn_all = QPushButton("전체"); btn_all.setFixedSize(50, 50); btn_all.setProperty("char_id", None); btn_all.clicked.connect(lambda: self.on_character_filter_clicked(None)); self.character_icon_layout.addWidget(btn_all); self.char_filter_buttons.append(btn_all)
        for char in self.game_data.get("characters", []): char_id = char.get("id"); char_name = char.get("name"); btn = QPushButton(char_name); btn.setFixedSize(50, 50); btn.setProperty("char_id", char_id); btn.clicked.connect(lambda _, c_id=char_id: self.on_character_filter_clicked(c_id)); self.character_icon_layout.addWidget(btn); self.char_filter_buttons.append(btn)
        self.update_filter_button_styles()
    def on_character_filter_clicked(self, char_id): self.current_char_filter = char_id; self.update_filter_button_styles(); self.refresh_all_potentials_list_in_deck_tab()
    def update_filter_button_styles(self): [btn.setStyleSheet(self.STYLE_ICON_SELECTED) if btn.property("char_id") == self.current_char_filter else btn.setStyleSheet(self.STYLE_ICON_DEFAULT) for btn in self.char_filter_buttons]
    def refresh_all_potentials_list_in_deck_tab(self):
        self.all_potentials_list.clear(); style_display_map = dict(STYLE_TYPES)
        for pot in self.game_data.get("potentials", []):
            pot_char_id = pot.get("character_id");
            if self.current_char_filter is not None and pot_char_id != self.current_char_filter: continue
            char_name = self.character_map.get(pot_char_id, "???"); style_key = pot.get("style_type"); style_display_name = style_display_map.get(style_key, "기타"); pot_name = pot.get("name"); display_text = f"[{char_name}] [{style_display_name}] {pot_name}"; list_item = QListWidgetItem(display_text); list_item.setData(Qt.ItemDataRole.UserRole, display_text); self.all_potentials_list.addItem(list_item)
    def add_deck(self):
        dialog = InputDialog("새 덱 생성", ["name"], parent=self);
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_data = dialog.get_data(); deck_name = new_data.get('name');
            if not deck_name: return
            if deck_name in self.user_decks: QMessageBox.warning(self, "알림", "이미 존재하는 덱 이름입니다."); return
            self.user_decks[deck_name] = {"name": deck_name, "potentials": []}; self.refresh_deck_list(); items = self.decks_list.findItems(deck_name, Qt.MatchFlag.MatchExactly);
            if items: self.decks_list.setCurrentItem(items[0])
    def del_deck(self):
        selected_item = self.decks_list.currentItem();
        if not selected_item: return
        deck_name = selected_item.text(); reply = QMessageBox.question(self, "삭제 확인", f"'{deck_name}' 덱을 정말 삭제하시겠습니까?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No);
        if reply == QMessageBox.StandardButton.Yes:
            if deck_name in self.user_decks: del self.user_decks[deck_name]
            self.refresh_deck_list(); self.on_deck_selected(None)
    def on_deck_selected(self, current_item, previous_item=None):
        self.current_deck_potentials_list.clear();
        if not current_item: self.deck_editor_label.setText("덱을 선택하세요"); self.on_character_filter_clicked(None); return
        deck_name = current_item.text(); self.deck_editor_label.setText(f"--- [{deck_name}] 편집 중 ---"); deck_data = self.user_decks.get(deck_name)
        if deck_data: [self.current_deck_potentials_list.addItem(QListWidgetItem(display_text)) for display_text in deck_data.get("potentials", [])]
    def add_potential_to_deck(self):
        selected_deck_item = self.decks_list.currentItem(); selected_potential_item = self.all_potentials_list.currentItem();
        if not selected_deck_item or not selected_potential_item: QMessageBox.warning(self, "알림", "덱과 추가할 잠재력을 모두 선택하세요."); return
        deck_name = selected_deck_item.text(); display_text = selected_potential_item.data(Qt.ItemDataRole.UserRole); deck_potentials = self.user_decks[deck_name].get("potentials", []);
        if display_text in deck_potentials: QMessageBox.information(self, "알림", "이미 덱에 포함된 잠재력입니다."); return
        self.user_decks[deck_name]["potentials"].append(display_text); self.current_deck_potentials_list.addItem(QListWidgetItem(display_text))
    def remove_potential_from_deck(self):
        selected_deck_item = self.decks_list.currentItem(); selected_deck_potential_item = self.current_deck_potentials_list.currentItem();
        if not selected_deck_item or not selected_deck_potential_item: QMessageBox.warning(self, "알림", "덱과 제거할 잠재력을 모두 선택하세요."); return
        deck_name = selected_deck_item.text(); display_text = selected_deck_potential_item.text();
        if display_text in self.user_decks[deck_name]["potentials"]: self.user_decks[deck_name]["potentials"].remove(display_text)
        self.current_deck_potentials_list.takeItem(self.current_deck_potentials_list.row(selected_deck_potential_item))
    def save_all_data(self):
        try:
            with open(GAMEDATA_FILE, 'w', encoding='utf-8') as f: json.dump(self.game_data, f, indent=2, ensure_ascii=False)
            with open(USERDECKS_FILE, 'w', encoding='utf-8') as f: json.dump(self.user_decks, f, indent=2, ensure_ascii=False)
            QMessageBox.information(self, "성공", f"{GAMEDATA_FILE} 와 {USERDECKS_FILE} 파일이 저장되었습니다.")
        except Exception as e: QMessageBox.critical(self, "오류", f"파일 저장 실패: {e}")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = DBEditorApp()
    ex.show()
    sys.exit(app.exec())