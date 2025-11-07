# tracker.py (v6.8 - 콤팩트 레이아웃 적용, 스탯 UI 재배치)
import sys
import json
import os
import re
import pytesseract
import keyboard
import numpy as np
import cv2
import Levenshtein
from PIL import Image, ImageGrab
from PIL.ImageQt import ImageQt
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
                             QPushButton, QLabel, QComboBox, QFormLayout,
                             QMessageBox, QListWidget, QListWidgetItem, QDialog,
                             QSplitter, QLineEdit, QDialogButtonBox, QTextEdit)
from PyQt6.QtCore import Qt, QTimer, QRect, pyqtSignal, QPoint
from PyQt6.QtGui import QPixmap, QPainter, QFont, QColor, QScreen, QPen
from common_utils import get_datafile_path, DataParser, GAMEDATA_FILE, USERDECKS_FILE, STYLE_TYPES

# --- (이전과 동일한 부분 생략) ---
def get_bundled_path(relative_path):
    try: base_path = sys._MEIPASS
    except Exception: base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

YOUR_TESSERACT_PATH = get_bundled_path(os.path.join('tesseract_bundle', 'tesseract.exe'))
CONFIG_FILE = get_datafile_path('config.json')
try:
    pytesseract.pytesseract.tesseract_cmd = YOUR_TESSERACT_PATH; pytesseract.get_tesseract_version()
except Exception as e:
    app_temp = QApplication(sys.argv); QMessageBox.critical(None, "치명적 오류", f"Tesseract 초기화 오류: {e}"); sys.exit()

class HotkeySettingsDialog(QDialog):
    def __init__(self, current_hotkeys, parent=None):
        super().__init__(parent); self.setWindowTitle("단축키 설정"); layout = QFormLayout(self); self.inputs = {}
        hotkey_map = {"ocr": "잠재력 확인:", "select1": "선택지 1 선택:", "select2": "선택지 2 선택:", "select3": "선택지 3 선택:"}
        for key, label in hotkey_map.items(): self.inputs[key] = QLineEdit(current_hotkeys.get(key, "")); layout.addRow(QLabel(label), self.inputs[key])
        info_label = QLabel("※ 키 이름은 'f10', 'ctrl+s' 와 같이 입력하세요.\n※ 변경사항은 프로그램을 재시작해야 적용됩니다."); info_label.setStyleSheet("font-size: 10px; color: gray;"); layout.addRow(info_label)
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel); button_box.accepted.connect(self.accept); button_box.rejected.connect(self.reject); layout.addWidget(button_box)
    def get_hotkeys(self): return {key: line_edit.text().strip().lower() for key, line_edit in self.inputs.items()}

class SetupWindow(QWidget):
    coordinates_saved = pyqtSignal(dict); cancelled = pyqtSignal()
    def __init__(self, pixmap, parent=None):
        super().__init__(parent); self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.FramelessWindowHint | Qt.WindowType.ToolTip); self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground); self.pixmap = pixmap; self.current_step = 1; self.boxes = {}; self.begin_pos = QPoint(); self.end_pos = QPoint(); self.setMouseTracking(True); self.showFullScreen(); self.activateWindow(); self.raise_()
    def paintEvent(self, event):
        try:
            painter = QPainter(self); painter.drawPixmap(self.rect(), self.pixmap); instruction_font = QFont('Malgun Gothic', 20, QFont.Weight.Bold); painter.setFont(instruction_font); text = f"[{self.current_step}/3] 번째 잠재력 영역을 드래그하세요. (취소는 [ESC] 키)"; fm = painter.fontMetrics(); text_rect = fm.boundingRect(QRect(), Qt.AlignmentFlag.AlignCenter, text); screen_geom = self.screen().geometry(); bg_rect = QRect(0, 50, screen_geom.width(), text_rect.height() + 20); painter.setBrush(QColor(0, 0, 0, 150)); painter.setPen(Qt.PenStyle.NoPen); painter.drawRect(bg_rect); painter.setPen(QColor(255, 0, 0)); painter.drawText(bg_rect, Qt.AlignmentFlag.AlignCenter, text)
            if not self.begin_pos.isNull() and not self.end_pos.isNull(): rect = QRect(self.begin_pos, self.end_pos).normalized(); painter.setPen(QPen(QColor(0, 255, 0, 200))); painter.setBrush(QColor(0, 255, 0, 50)); painter.drawRect(rect)
        except Exception as e: print(f"Paint Event Error: {e}")
    def mousePressEvent(self, event): self.begin_pos = event.pos(); self.end_pos = event.pos(); self.update()
    def mouseMoveEvent(self, event):
        if not self.begin_pos.isNull(): self.end_pos = event.pos(); self.update()
    def mouseReleaseEvent(self, event):
        if self.begin_pos.isNull(): return
        rect = QRect(self.begin_pos, self.end_pos).normalized()
        if rect.width() < 10 or rect.height() < 10: self.begin_pos = QPoint(); self.end_pos = QPoint(); self.update(); return
        box_coords = (rect.left(), rect.top(), rect.right(), rect.bottom()); self.boxes[f"box{self.current_step}"] = box_coords; self.current_step += 1; self.begin_pos = QPoint(); self.end_pos = QPoint()
        if self.current_step > 3: self.coordinates_saved.emit(self.boxes); self.close()
        else: self.update()
    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape: self.cancelled.emit(); self.close()

class TrackerApp(QWidget):
    ocr_requested = pyqtSignal(); selection_requested = pyqtSignal(int)
    def __init__(self):
        super().__init__()
        self.data_parser = DataParser()
        self.game_data={}; self.user_decks={}; self.coordinates={}; self.hotkeys={}; self.potential_lookup={}
        self.setup_window=None
        self.chosen_potentials_in_run = {} # (★수정★) set -> dict
        self.last_selected_deck=None; self.ocr_results=[None, None, None]; self.current_run_stats={}
        self.ocr_requested.connect(self.run_ocr_check); self.selection_requested.connect(self.select_potential)

        # (★★ 수정 ★★) 초기화 순서 변경: 데이터 로드 -> UI 생성 -> 설정 로드 -> 덱 선택
        self.load_all_data() # self.game_data, self.user_decks 로드
        self.initUI() # UI 구성 (self.user_decks 사용)
        self.load_config() # self.coordinates, self.hotkeys, self.last_selected_deck 로드 (UI 생성 후)

        if self.last_selected_deck and self.deck_select_combo.findText(self.last_selected_deck) != -1:
            self.deck_select_combo.setCurrentText(self.last_selected_deck)
        elif self.deck_select_combo.count() > 0:
            self.deck_select_combo.setCurrentIndex(0)
        
        # 콤보박스 설정 후, on_deck_changed를 명시적으로 호출하여 덱 데이터를 로드
        self.on_deck_changed(self.deck_select_combo.currentText())

    def reload_all_data_and_decks(self):
        """에디터에서 저장 후 호출될 데이터 리로드 함수"""
        print("에디터 저장 감지: 데이터 및 덱 새로고침")
        self.load_all_data()
        self.reload_decks()

    def load_all_data(self):
        try:
            with open(GAMEDATA_FILE, 'r', encoding='utf-8') as f: self.game_data = json.load(f)
            with open(USERDECKS_FILE, 'r', encoding='utf-8') as f: self.user_decks = json.load(f)
            self._create_potential_lookup_table()
        except Exception as e: self.show_error_message(f"데이터 로드 오류: {e}")

    def reload_decks(self):
        """덱 목록을 새로고침하고, 마지막 선택된 덱을 다시 선택합니다."""
        current_deck = self.deck_select_combo.currentText()
        self.deck_select_combo.clear()
        
        if self.user_decks:
            self.deck_select_combo.addItems(self.user_decks.keys())
            if current_deck in self.user_decks:
                self.deck_select_combo.setCurrentText(current_deck) # 이전 덱 유지
            elif self.deck_select_combo.count() > 0:
                self.deck_select_combo.setCurrentIndex(0) # 첫 번째 덱
        else:
            self.deck_select_combo.addItem("불러온 덱 없음")
        
        # 덱 변경이 실제로 일어났는지와 관계없이 UI 업데이트 강제 실행
        self.on_deck_changed(self.deck_select_combo.currentText())

    def _create_potential_lookup_table(self):
        self.potential_lookup = {}; character_map = {c['id']: c['name'] for c in self.game_data.get('characters', [])}; style_map = dict(STYLE_TYPES)
        for p in self.game_data.get("potentials", []):
            key = f"[{character_map.get(p.get('character_id'), '?')}] [{style_map.get(p.get('style_type'), '?')}] {p.get('name')}"
            self.potential_lookup[key] = p

    # (★★ 추가 ★★) config.json 로드 함수
    def load_config(self):
        try:
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
                    self.coordinates = config_data.get("coordinates", {})
                    self.hotkeys = config_data.get("hotkeys", {})
                    self.last_selected_deck = config_data.get("last_selected_deck")
            else:
                # 파일이 없을 경우 기본값
                self.coordinates = {}
                self.hotkeys = {"ocr": "f10", "select1": "f1", "select2": "f2", "select3": "f3"} # 기본값 예시
                self.last_selected_deck = None
            
            # UI 업데이트 (initUI에서 생성된 위젯 사용)
            if self.coordinates and len(self.coordinates) == 3:
                self.config_status_label.setText("좌표 설정됨 (3/3)")
            else:
                self.config_status_label.setText("좌표 설정 필요 (좌표 설정 버튼)")
            
            self.run_button.setText(self.run_button_text_template.format(self.hotkeys.get('ocr', 'N/A')))
            
        except Exception as e:
            self.show_error_message(f"config.json 로드 오류: {e}")
            self.coordinates = {}
            self.hotkeys = {}
            self.last_selected_deck = None

    # (★★ 추가 ★★) config.json 저장 함수
    def save_config(self):
        try:
            config_data = {
                "coordinates": self.coordinates,
                "hotkeys": self.hotkeys,
                "last_selected_deck": self.last_selected_deck
            }
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=2, ensure_ascii=False)
            print("설정 저장됨:", CONFIG_FILE)
        except Exception as e:
            self.show_error_message(f"config.json 저장 오류: {e}")

    # (★수정★) 잠재력 선택(레벨 업) 로직 변경
    def select_potential(self, index):
        if not (0 <= index < 3 and self.ocr_results and self.ocr_results[index]): return

        potential_to_add_str = self.ocr_results[index]
        
        # 현재 레벨 확인 및 최대 레벨(6) 제한
        current_level = self.chosen_potentials_in_run.get(potential_to_add_str, 0)
        if current_level >= 6:
            print(f"'{potential_to_add_str}'은(는) 이미 최대 레벨(6)입니다.")
            QMessageBox.information(self, "알림", f"'{self.extract_potential_name(potential_to_add_str)}'은(는)\n이미 최대 레벨입니다.")
            return

        # 레벨 업 및 스탯 합산
        self.chosen_potentials_in_run[potential_to_add_str] = current_level + 1
        print(f"'{potential_to_add_str}' 선택됨. 레벨: {current_level + 1}")
        
        potential_data = self.potential_lookup.get(potential_to_add_str)
        if potential_data:
            new_stats = self._parse_potential_effects(potential_data)
            for stat_name, value in new_stats.items():
                self.current_run_stats[stat_name] = self.current_run_stats.get(stat_name, 0) + value
            
            # (★★ 수정 ★★) 스탯 UI 업데이트 함수 호출
            self.update_stats_display()

        self.update_tracking_display()
    
    # (★수정★) 스탯 해석기에 effects 필드 처리 로직 명시적으로 추가
    def _parse_potential_effects(self, pot_data):
        all_stats = {}
        if not pot_data: return {}

        # 1. 'effects' 필드 (사용자 직접 입력) 처리
        for effect in pot_data.get('effects', []):
            stat_name = effect.get("type")
            value = effect.get("value", 0)
            if stat_name and isinstance(value, (int, float)):
                all_stats[stat_name] = all_stats.get(stat_name, 0) + value
        
        # 2. 'params' 필드 (데이터 파일 기반 파싱) 처리
        for param_str in pot_data.get('params', []):
            parsed_stat = self.data_parser.parse_param(param_str)
            if parsed_stat:
                stat_name = parsed_stat["type"]
                value = parsed_stat["value"]
                all_stats[stat_name] = all_stats.get(stat_name, 0) + value
        
        if all_stats: print(f"'{pot_data.get('name')}' 스탯 해석 결과: {all_stats}")
        return all_stats

    # (★수정★) 목록 업데이트 시 레벨 표시
    def update_tracking_display(self):
        self.not_chosen_list.clear(); self.chosen_list.clear()
        
        # 선택된 잠재력 목록 (레벨과 함께 표시)
        for potential, level in self.chosen_potentials_in_run.items():
            item_text = f"{potential} [Lv.{level}]"
            item = QListWidgetItem(item_text)
            pot_data = self.potential_lookup.get(potential)
            if pot_data:
                effects = self._parse_potential_effects(pot_data)
                tooltip_text = "\n".join([f"- {name}: {value}" for name, value in effects.items()])
                if tooltip_text: item.setToolTip(f"1회당 효과:\n{tooltip_text}")
            self.chosen_list.addItem(item)
            
        # 미선택 잠재력 목록
        if isinstance(self.current_deck_potentials, list):
            for potential in self.current_deck_potentials:
                if potential not in self.chosen_potentials_in_run:
                    item = QListWidgetItem(potential)
                    pot_data = self.potential_lookup.get(potential)
                    if pot_data:
                        effects = self._parse_potential_effects(pot_data)
                        tooltip_text = "\n".join([f"- {name}: {value}" for name, value in effects.items()])
                        if tooltip_text: item.setToolTip(f"효과:\n{tooltip_text}")
                    self.not_chosen_list.addItem(item)

    def on_deck_changed(self, deck_name):
        if deck_name in self.user_decks:
            self.current_deck_potentials = self.user_decks[deck_name].get("potentials", [])
            if self.last_selected_deck != deck_name:
                self.last_selected_deck = deck_name
                self.save_config() # 덱 선택 변경 시에만 저장
        else:
            # 덱이 없는 경우 (예: "불러온 덱 없음")
            self.current_deck_potentials = []
            if self.last_selected_deck is not None:
                self.last_selected_deck = None
                self.save_config() # 덱 선택이 해제되었으므로 저장

        self._reset_run_data() # 덱이 변경되면 항상 런 데이터 리셋

    # --- (★★ 수정 ★★) initUI 레이아웃 전체 재배치 ---
    def initUI(self):
        main_vbox = QVBoxLayout()
        main_vbox.setSpacing(10) # 위젯 간 간격
        main_vbox.setContentsMargins(10, 10, 10, 10) # 창 내부 여백

        # 1. 덱 선택
        deck_select_layout = QHBoxLayout(); self.deck_select_label = QLabel("적용할 덱:"); self.deck_select_combo = QComboBox(self)
        if self.user_decks: self.deck_select_combo.addItems(self.user_decks.keys())
        else: self.deck_select_combo.addItem("불러온 덱 없음")
        self.deck_select_combo.textActivated.connect(self.on_deck_changed); self.reload_deck_button = QPushButton("덱 새로고침"); self.reload_deck_button.clicked.connect(self.reload_decks); deck_select_layout.addWidget(self.deck_select_label); deck_select_layout.addWidget(self.deck_select_combo, 1); deck_select_layout.addWidget(self.reload_deck_button); 
        main_vbox.addLayout(deck_select_layout)
        
        # 2. OCR 실행 버튼
        self.run_button_text_template = "현재 잠재력 확인 ({})"; self.run_button = QPushButton(self.run_button_text_template.format("..."), self); self.run_button.clicked.connect(self.run_ocr_check); 
        self.run_button.setStyleSheet("font-size: 15px; padding: 8px;"); 
        main_vbox.addWidget(self.run_button)
        
        # 3. 설정 버튼
        setup_layout = QHBoxLayout(); self.setup_button = QPushButton("좌표 설정 다시하기", self); self.setup_button.clicked.connect(self.launch_coord_setup_from_button); self.config_status_label = QLabel("상태: 로딩 중..."); self.hotkey_button = QPushButton("단축키 설정", self); self.hotkey_button.clicked.connect(self.open_hotkey_settings); self.reset_button = QPushButton("현재 런 리셋", self); self.reset_button.clicked.connect(self.reset_tracking);
        setup_layout.addWidget(self.setup_button); setup_layout.addWidget(self.hotkey_button); setup_layout.addWidget(self.config_status_label, 1); setup_layout.addWidget(self.reset_button); 
        main_vbox.addLayout(setup_layout)
        
        # 4. 선택지 1, 2, 3
        results_vbox = QVBoxLayout(); results_vbox.setSpacing(5); 
        label_style = "font-size: 13px; padding: 4px; color: black; border: 1px solid #ddd; background-color: #f9f9f9;"; 
        button_size = 40 
        
        hbox1 = QHBoxLayout(); label1 = QLabel("선택지 1:"); self.result_label_1 = QLabel("-"); self.result_label_1.setStyleSheet(label_style); self.result_label_1.setFixedHeight(button_size); self.result_label_1.setAlignment(Qt.AlignmentFlag.AlignCenter); self.select_btn_1 = QPushButton("-"); self.select_btn_1.setFixedSize(button_size, button_size); self.select_btn_1.clicked.connect(lambda: self.select_potential(0)); hbox1.addWidget(label1); hbox1.addWidget(self.result_label_1, 1); hbox1.addWidget(self.select_btn_1); results_vbox.addLayout(hbox1)
        hbox2 = QHBoxLayout(); label2 = QLabel("선택지 2:"); self.result_label_2 = QLabel("-"); self.result_label_2.setStyleSheet(label_style); self.result_label_2.setFixedHeight(button_size); self.result_label_2.setAlignment(Qt.AlignmentFlag.AlignCenter); self.select_btn_2 = QPushButton("-"); self.select_btn_2.setFixedSize(button_size, button_size); self.select_btn_2.clicked.connect(lambda: self.select_potential(1)); hbox2.addWidget(label2); hbox2.addWidget(self.result_label_2, 1); hbox2.addWidget(self.select_btn_2); results_vbox.addLayout(hbox2)
        hbox3 = QHBoxLayout(); label3 = QLabel("선택지 3:"); self.result_label_3 = QLabel("-"); self.result_label_3.setStyleSheet(label_style); self.result_label_3.setFixedHeight(button_size); self.result_label_3.setAlignment(Qt.AlignmentFlag.AlignCenter); self.select_btn_3 = QPushButton("-"); self.select_btn_3.setFixedSize(button_size, button_size); self.select_btn_3.clicked.connect(lambda: self.select_potential(2)); hbox3.addWidget(label3); hbox3.addWidget(self.result_label_3, 1); hbox3.addWidget(self.select_btn_3); results_vbox.addLayout(hbox3)
        main_vbox.addLayout(results_vbox); 
        
        # 5. 미선택 / 선택 완료 리스트 (좌우 배치)
        list_layout = QHBoxLayout()
        
        # 미선택 잠재력
        not_chosen_widget = QWidget(); 
        not_chosen_layout = QVBoxLayout(not_chosen_widget); 
        not_chosen_layout.addWidget(QLabel("미선택 잠재력")); 
        self.not_chosen_list = QListWidget(); 
        not_chosen_layout.addWidget(self.not_chosen_list); 
        list_layout.addWidget(not_chosen_widget) # QHBoxLayout에 추가
        
        # 선택 완료 잠재력
        chosen_widget = QWidget(); 
        chosen_layout = QVBoxLayout(chosen_widget); 
        chosen_layout.addWidget(QLabel("선택 완료 잠재력")); 
        self.chosen_list = QListWidget(); 
        chosen_layout.addWidget(self.chosen_list); 
        list_layout.addWidget(chosen_widget) # QHBoxLayout에 추가

        # (★★ 수정 ★★) 리스트 위젯이 스탯창보다 더 많은 공간을 차지하도록 설정
        # main_vbox.addLayout(list_layout, 1) # 1의 비율로 공간 차지
        main_vbox.addLayout(list_layout)


        # 6. 현재 런 스탯 총합 (맨 아래)
        stats_layout = QFormLayout(); 
        stats_layout.setContentsMargins(5, 10, 5, 5); 
        self.stats_display = QTextEdit(); 
        self.stats_display.setReadOnly(True); 
        
        # (★★ 수정 ★★) 스탯 창의 높이를 90으로 고정 (ui6.png 참고)
        self.stats_display.setFixedHeight(90); 
        
        self.stats_display.setStyleSheet("font-size: 12px; background-color: #f0f0f0;"); 
        stats_layout.addRow(QLabel("--- 현재 런 스탯 총합 ---"), self.stats_display); 
        main_vbox.addLayout(stats_layout) # 메인 VBox에 스탯 레이아웃 추가

        # (★★ 수정 ★★) 리스트가 남은 공간을 모두 차지하도록 함
        # main_vbox.addStretch(1) # 이 부분은 레이아웃에 따라 조정
        
        self.setLayout(main_vbox); self.setWindowTitle('스텔라 소라 트래커 (v6.8)'); 
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
    
    def reset_tracking(self):
        """현재 런 리셋 버튼에 연결된 함수"""
        reply = QMessageBox.question(self, "확인", "현재 런의 잠재력 선택과 스탯을 초기화하시겠습니까?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self._reset_run_data()
            print("런 데이터 리셋됨.")

    def _reset_run_data(self):
        self.chosen_potentials_in_run.clear(); self.current_run_stats.clear(); 
        
        # (★★ 수정 ★★) 스탯 UI 업데이트 함수 호출
        self.update_stats_display(); 
        
        self.update_tracking_display()
        label_style = "font-size: 13px; padding: 4px; color: black; border: 1px solid #ddd; background-color: #f9f9f9;";
        for label, btn in [(self.result_label_1, self.select_btn_1), (self.result_label_2, self.select_btn_2), (self.result_label_3, self.select_btn_3)]: label.setText("-"); label.setStyleSheet(label_style); btn.setText("-")
        self.ocr_results = [None, None, None]
    
    # (★★ 수정 ★★) 스탯 UI 업데이트 함수
    def update_stats_display(self):
        if not self.current_run_stats: 
            self.stats_display.setText("선택된 잠재력 없음"); 
            return
        display_text = "";
        for stat_name, value in sorted(self.current_run_stats.items()): 
            value_str = f"{int(value)}" if value == int(value) else f"{value:.1f}"; 
            display_text += f"{stat_name}: +{value_str}\n"
        self.stats_display.setText(display_text.strip())
    
    def open_hotkey_settings(self):
        dialog = HotkeySettingsDialog(self.hotkeys, self);
        if dialog.exec():
            new_hotkeys = dialog.get_hotkeys()
            if all(new_hotkeys.values()): self.hotkeys = new_hotkeys; self.save_config(); self.run_button.setText(self.run_button_text_template.format(self.hotkeys.get('ocr', 'N/A'))); QMessageBox.information(self, "알림", "단축키 설정이 저장되었습니다.\n프로그램을 재시작해야 적용됩니다.")
            else: QMessageBox.warning(self, "오류", "단축키는 비워둘 수 없습니다.")
    
    def launch_coord_setup_from_button(self):
        QMessageBox.information(self, "알림", "지금부터 [캡처 영역 설정]을 시작합니다.\n\n2초 안에 게임의 [잠재력 선택 화면]으로 이동하세요.\n\n(전체 화면 모드에서만 정상 동작합니다)")
        # (★★ 수정 ★★) hide() 대신 부모 윈도우(메인 윈도우)를 숨김
        parent_window = self.window()
        if parent_window:
            parent_window.hide()
        
        QTimer.singleShot(2000, self.launch_coord_setup)
    
    def launch_coord_setup(self):
        try:
            screen = QApplication.primaryScreen();
            if not screen:
                self.show_error_message("주 스크린을 찾을 수 없습니다.")
                parent_window = self.window();
                if parent_window: parent_window.show()
                return
            
            pixmap = screen.grabWindow(0)
            if pixmap.isNull():
                self.show_error_message("스크린샷 캡처에 실패했습니다.\n(게임이 전체화면이 아닐 수 있습니다)")
                parent_window = self.window();
                if parent_window: parent_window.show()
                return
            
            self.setup_window = SetupWindow(pixmap, self)
            self.setup_window.coordinates_saved.connect(self.on_setup_complete)
            self.setup_window.cancelled.connect(self.on_setup_cancelled)
        
        except Exception as e:
            self.show_error_message(f"좌표 설정 창 생성 중 예외 발생: {e}")
            parent_window = self.window();
            if parent_window: parent_window.show()

    def on_setup_complete(self, coordinates):
        self.coordinates = coordinates
        self.save_config()
        self.load_config() # 저장 후 바로 다시 로드하여 UI 상태 업데이트
        QMessageBox.information(self, "성공", "캡처 영역 설정이 저장되었습니다.")
        parent_window = self.window();
        if parent_window: parent_window.show()
        self.setup_window = None

    def on_setup_cancelled(self):
        self.show_error_message("좌표 설정이 취소되었습니다.")
        self.load_config() # UI 상태 복원
        parent_window = self.window();
        if parent_window: parent_window.show()
        self.setup_window = None

    def run_ocr_check(self):
        if not all(k in self.coordinates for k in ['box1', 'box2', 'box3']):
            self.show_error_message("캡처 좌표가 설정되지 않았습니다.\n[좌표 설정 다시하기] 버튼으로 설정해주세요.")
            return
        
        try:
            coords = self.coordinates; tess_config = '--psm 7 --oem 1'; final_texts = []
            
            for i in range(3):
                box_key = f'box{i+1}'
                if box_key not in coords:
                    print(f"오류: {box_key} 좌표 없음")
                    final_texts.append("")
                    continue
                
                pil_img = ImageGrab.grab(bbox=coords[box_key]);
                processed_images = self.get_processed_images(pil_img);
                candidate_texts = set()
                
                for proc_img in processed_images:
                    text = pytesseract.image_to_string(proc_img, lang='kor', config=tess_config).strip()
                    if text: candidate_texts.add(text)
                
                best_text = ""; highest_similarity = 0.0
                if not candidate_texts:
                    final_texts.append(""); continue
                
                for ocr_text in candidate_texts:
                    ocr_compare = self.clean_text_for_comparison(ocr_text)
                    if not ocr_compare: continue
                    
                    for deck_potential_raw in self.current_deck_potentials:
                        deck_compare = self.clean_text_for_comparison(self.extract_potential_name(deck_potential_raw))
                        if not deck_compare: continue
                        
                        similarity = Levenshtein.ratio(ocr_compare, deck_compare)
                        
                        if similarity > highest_similarity:
                            highest_similarity = similarity
                            best_text = ocr_text
                            
                # 매칭 기준(0.6) 미만이면, 가장 긴 텍스트를 대신 사용 (오매칭 방지)
                if highest_similarity < 0.6:
                    best_text = max(candidate_texts, key=len) if candidate_texts else ""
                    
                print(f"선택지 {i+1} 후보: {list(candidate_texts)} -> 최종 선택: '{best_text}' (유사도: {highest_similarity:.2%})");
                final_texts.append(best_text)
                
        except Exception as e:
            self.show_error_message(f"OCR/스크린샷 오류: {e}"); return

        self.ocr_results = [None, None, None]; labels, buttons = [self.result_label_1, self.result_label_2, self.result_label_3], [self.select_btn_1, self.select_btn_2, self.select_btn_3]
        for i, text_raw in enumerate(final_texts):
            matched = self.update_result_label(labels[i], text_raw)
            if matched:
                self.ocr_results[i] = matched; buttons[i].setText("OK!")
            else:
                buttons[i].setText("No!")
    
    def get_processed_images(self, pil_img):
        try:
            image = np.array(pil_img); image_bgr = cv2.cvtColor(image, cv2.COLOR_RGB2BGR); scale = 3.0; width = int(image.shape[1] * scale); height = int(image.shape[0] * scale); resized = cv2.resize(image_bgr, (width, height), interpolation=cv2.INTER_LANCZOS4)
            processed_images = []; b, g, r = cv2.split(resized); normalized = cv2.normalize(b, None, 0, 255, cv2.NORM_MINMAX)
            for th_val in [120, 150, 180]: _, binary_a = cv2.threshold(normalized, th_val, 255, cv2.THRESH_BINARY); processed_images.append(binary_a)
            gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY); edges = cv2.Canny(gray, 50, 150); kernel = np.ones((2,2), np.uint8); dilated = cv2.dilate(edges, kernel, iterations=1); processed_images.append(cv2.bitwise_not(dilated))
            return processed_images
        except Exception as e: print(f"디버그: 이미지 전처리 중 오류: {e}"); return [pil_img]
    
    def update_result_label(self, label_widget, ocr_text_raw):
        best_match_potential = None; highest_similarity = 0.6; ocr_compare_text = re.sub(r'[^\w\s가-힣.•]', '', ocr_text_raw).replace(" ", "")
        
        if ocr_compare_text and isinstance(self.current_deck_potentials, list):
            for deck_potential_raw in self.current_deck_potentials:
                potential_name_only = self.extract_potential_name(deck_potential_raw); deck_compare_text = self.clean_text_for_comparison(potential_name_only)
                if not deck_compare_text: continue
                
                similarity = Levenshtein.ratio(ocr_compare_text, deck_compare_text)
                
                if similarity > highest_similarity:
                    highest_similarity = similarity
                    best_match_potential = deck_potential_raw
        
        style_highlight = "font-size: 16px; padding: 5px; color: green; font-weight: bold; border: 1px solid #ddd; background-color: #f9f9f9;"; 
        style_normal = "font-size: 13px; padding: 4px; color: black; border: 1px solid #ddd; background-color: #f9f9f9;"; 
        style_error = "font-size: 13px; padding: 4px; color: gray; border: 1px solid #ddd; background-color: #f9f9f9;"
        
        if best_match_potential:
            label_widget.setText(f"★ {self.extract_potential_name(best_match_potential)} ★"); label_widget.setStyleSheet(style_highlight)
            label_widget.setToolTip(f"인식된 텍스트: {ocr_text_raw}\n유사도: {highest_similarity:.2%}")
        else:
            label_widget.setToolTip(f"인식된 텍스트 원본:\n{ocr_text_raw}"); label_widget.setText(ocr_text_raw if ocr_text_raw else "(인식 실패)"); label_widget.setStyleSheet(style_error if not ocr_text_raw else style_normal)
        
        return best_match_potential
    
    def clean_text_for_comparison(self, text): return "".join(re.findall(r'[가-힣]+', text or ""))
    def extract_potential_name(self, deck_potential_raw): return deck_potential_raw.split('] ')[-1] if '] ' in deck_potential_raw else deck_potential_raw
    def show_error_message(self, message): print(f"오류: {message}"); QMessageBox.warning(self, "오류", message)


     # 이 파일은 이제 단독으로 실행되지 않습니다. 'Mao-chan_Helper.py'를 실행하세요.