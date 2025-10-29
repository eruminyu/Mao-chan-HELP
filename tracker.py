# tracker.py (v5.9 - 모든 기능 통합 최종본)
import sys
import json
import os
import time
import re
import pygetwindow as gw
import pytesseract
import keyboard # <<< import 구문 포함
from PIL import Image, ImageGrab, ImageOps
from PIL.ImageQt import ImageQt
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
                             QPushButton, QLabel, QComboBox, QFormLayout,
                             QMessageBox, QListWidget, QListWidgetItem, QDialog,
                             QSizePolicy, QSplitter)
from PyQt6.QtCore import Qt, QTimer, QRect, pyqtSignal, QPoint, QRectF
from PyQt6.QtGui import QPixmap, QPainter, QFont, QColor, QBrush, QPen, QScreen, QKeySequence

# --- 경로 설정 함수 ---
def get_bundled_path(relative_path):
    try: base_path = sys._MEIPASS
    except Exception: base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)
def get_datafile_path(relative_path):
    if getattr(sys, 'frozen', False): base_path = os.path.dirname(sys.executable)
    else: base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)
# --------------------

# --- 설정 ---
YOUR_TESSERACT_PATH = get_bundled_path(os.path.join('tesseract_bundle', 'tesseract.exe'))
CONFIG_FILE = get_datafile_path('config.json')
GAMEDATA_FILE = get_datafile_path('gamedata.json')
USERDECKS_FILE = get_datafile_path('user_decks.json')

# --- Tesseract 검사 ---
try:
    pytesseract.pytesseract.tesseract_cmd = YOUR_TESSERACT_PATH
    pytesseract.get_tesseract_version()
except Exception as e:
    app_temp = QApplication(sys.argv); QMessageBox.critical(None, "치명적 오류", f"Tesseract 초기화 오류: {e}\ntesseract_bundle 폴더나 경로를 확인하세요."); sys.exit()
# --------------------

# --- 2단계: 캡처 영역 설정 ---
class SetupWindow(QWidget):
    coordinates_saved = pyqtSignal(dict); cancelled = pyqtSignal()
    def __init__(self, screenshot):
        super().__init__()
        try:
            self.screenshot = screenshot
            if isinstance(screenshot, Image.Image): self.qt_image = ImageQt(self.screenshot); self.pixmap = QPixmap.fromImage(self.qt_image)
            else: self.pixmap = QPixmap(); print("오류: 스크린샷 객체 타입 오류")
            self.current_step = 1; self.boxes = {}; self.begin_pos = QPoint(); self.end_pos = QPoint(); self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.FramelessWindowHint); self.showFullScreen();
            if not self.isFullScreen(): print("경고: 전체 화면 모드 진입 실패."); self.showMaximized()
            self.setWindowOpacity(0.7); self.setMouseTracking(True); print("SetupWindow 생성 및 표시 성공")
        except Exception as e: print(f"SetupWindow 생성 오류: {e}"); QMessageBox.critical(None, "오류", f"캡처 설정 창 생성 실패: {e}\n프로그램을 다시 시작해주세요."); QTimer.singleShot(100, self.cancelled.emit); QTimer.singleShot(150, self.close)
    def paintEvent(self, event):
        try:
            painter = QPainter(self); painter.drawPixmap(self.rect(), self.pixmap); instruction_font = QFont('Malgun Gothic', 20, QFont.Weight.Bold); painter.setFont(instruction_font); text = f"[{self.current_step}/3] 번째 잠재력 영역을 드래그하세요. (취소는 [ESC] 키)"; fm = painter.fontMetrics(); text_bounding_rect = fm.boundingRect(text); bg_width = text_bounding_rect.width() + 40; bg_height = text_bounding_rect.height() + 10; screen = QApplication.primaryScreen();
            if screen: screen_geometry = screen.geometry(); screen_center_x = screen_geometry.width() // 2
            else: screen_center_x = self.width() // 2
            bg_x = screen_center_x - bg_width // 2; bg_y = 50; draw_rect = QRect(bg_x, bg_y, bg_width, bg_height); painter.setBrush(QColor(0, 0, 0, 150)); painter.setPen(Qt.PenStyle.NoPen); painter.drawRect(draw_rect); painter.setPen(QColor(255, 0, 0)); painter.drawText(draw_rect, Qt.AlignmentFlag.AlignCenter, text);
            if not self.begin_pos.isNull() and not self.end_pos.isNull(): rect = QRect(self.begin_pos, self.end_pos).normalized(); green_pen = QPen(QColor(0, 255, 0, 200)); painter.setPen(green_pen); painter.setBrush(QColor(0, 255, 0, 50)); painter.drawRect(rect)
            painter.end()
        except Exception as e: print(f"paintEvent 오류: {e}")
    def mousePressEvent(self, event): self.begin_pos = event.pos(); self.end_pos = event.pos(); self.update()
    def mouseMoveEvent(self, event):
        if not self.begin_pos.isNull(): self.end_pos = event.pos(); self.update()
    def mouseReleaseEvent(self, event):
        if self.begin_pos.isNull(): return
        self.end_pos = event.pos(); rect = QRect(self.begin_pos, self.end_pos).normalized()
        if rect.width() < 10 or rect.height() < 10: self.begin_pos = QPoint(); self.end_pos = QPoint(); self.update(); return
        box_coords = (rect.left(), rect.top(), rect.right(), rect.bottom()); self.boxes[f"box{self.current_step}"] = box_coords
        self.current_step += 1; self.begin_pos = QPoint(); self.end_pos = QPoint()
        if self.current_step > 3: self.coordinates_saved.emit(self.boxes); self.close()
        else: self.update()
    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape: self.cancelled.emit(); self.close()

# --- 3. 메인 트래커 앱 ---
class TrackerApp(QWidget):
    ocr_requested = pyqtSignal(); selection_requested = pyqtSignal(int)
    def __init__(self):
        super().__init__(); self.game_data = {}; self.user_decks = {}; self.coordinates = {}; self.setup_window = None; self.chosen_potentials_in_run = set(); self.last_selected_deck = None; self.ocr_results = [None, None, None];
        self.ocr_requested.connect(self.run_ocr_check); self.selection_requested.connect(self.select_potential);
        self.load_all_data(); self.initUI(); self.load_config();
        if self.last_selected_deck and self.last_selected_deck in self.user_decks: self.deck_select_combo.setCurrentText(self.last_selected_deck); self.on_deck_changed(self.last_selected_deck)
        elif self.deck_select_combo.count() > 0: first_deck = self.deck_select_combo.itemText(0); self.deck_select_combo.setCurrentText(first_deck); self.on_deck_changed(first_deck)
        else: self.update_tracking_display()

    def load_all_data(self):
        try:
            with open(GAMEDATA_FILE, 'r', encoding='utf-8') as f: self.game_data = json.load(f)
            with open(USERDECKS_FILE, 'r', encoding='utf-8') as f: self.user_decks = json.load(f)
        except FileNotFoundError as e: self.show_error_message(f"데이터 파일({e.filename})을 찾을 수 없습니다.")
        except Exception as e: self.show_error_message(f"데이터 로드 오류: {e}")
    def load_config(self):
        config_loaded = False
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f: config_data = json.load(f)
                self.coordinates = config_data.get("coordinates", {}); self.last_selected_deck = config_data.get("last_selected_deck", None)
                if 'box1' in self.coordinates and 'box2' in self.coordinates and 'box3' in self.coordinates: print(f"좌표 로드 성공: {self.coordinates}"); self.run_button.setEnabled(True); self.config_status_label.setText("상태: 좌표 설정 완료"); self.config_status_label.setStyleSheet("color: green;"); config_loaded = True
                else: print("config.json 파일은 있으나 좌표 데이터가 불완전합니다."); self.coordinates = {}
            except Exception as e: self.show_error_message(f"config.json 읽기 오류: {e}\n설정을 다시 진행해야 할 수 있습니다."); self.coordinates = {}; self.last_selected_deck = None
        if not config_loaded: self.run_button.setEnabled(False); self.config_status_label.setText("상태: 캡처 영역 설정 필요"); self.config_status_label.setStyleSheet("color: red;")
        return config_loaded
    def save_config(self):
        try:
            config_data = {"coordinates": self.coordinates, "last_selected_deck": self.deck_select_combo.currentText()};
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f: json.dump(config_data, f, indent=2)
            print("config.json 저장 완료.")
        except Exception as e: self.show_error_message(f"config.json 저장 실패: {e}")

    def initUI(self):
        # (v5.8 UI 적용)
        main_vbox = QVBoxLayout()
        deck_select_layout = QHBoxLayout(); self.deck_select_label = QLabel("적용할 덱:"); self.deck_select_combo = QComboBox(self);
        if self.user_decks: self.deck_select_combo.addItems(self.user_decks.keys())
        else: self.deck_select_combo.addItem("불러온 덱 없음")
        self.deck_select_combo.textActivated.connect(self.on_deck_changed); self.reload_deck_button = QPushButton("덱 새로고침"); self.reload_deck_button.clicked.connect(self.reload_decks); deck_select_layout.addWidget(self.deck_select_label); deck_select_layout.addWidget(self.deck_select_combo, 1); deck_select_layout.addWidget(self.reload_deck_button); main_vbox.addLayout(deck_select_layout)
        self.run_button = QPushButton("현재 잠재력 확인 (F10)", self); self.run_button.clicked.connect(self.run_ocr_check); self.run_button.setStyleSheet("font-size: 16px; padding: 10px;"); main_vbox.addWidget(self.run_button)
        setup_layout = QHBoxLayout(); self.setup_button = QPushButton("좌표 설정 다시하기", self); self.setup_button.clicked.connect(self.launch_coord_setup_from_button); self.config_status_label = QLabel("상태: 로딩 중..."); self.reset_button = QPushButton("현재 런 리셋", self); self.reset_button.clicked.connect(self.reset_tracking); setup_layout.addWidget(self.setup_button); setup_layout.addWidget(self.config_status_label, 1); setup_layout.addWidget(self.reset_button); main_vbox.addLayout(setup_layout)
        results_vbox = QVBoxLayout(); results_vbox.setSpacing(5) # 간격 5
        label_style = "font-size: 14px; padding: 5px; color: black; border: 1px solid #ddd; background-color: #f9f9f9;"
        button_size = 50
        # 선택지 1
        hbox1 = QHBoxLayout(); label1 = QLabel("선택지 1:"); self.result_label_1 = QLabel("-");
        self.result_label_1.setStyleSheet(label_style); self.result_label_1.setFixedHeight(button_size); self.result_label_1.setAlignment(Qt.AlignmentFlag.AlignCenter);
        self.select_btn_1 = QPushButton("-"); self.select_btn_1.setFixedSize(button_size, button_size); self.select_btn_1.clicked.connect(lambda: self.select_potential(0));
        hbox1.addWidget(label1); hbox1.addWidget(self.result_label_1, 1); hbox1.addWidget(self.select_btn_1); results_vbox.addLayout(hbox1)
        # 선택지 2
        hbox2 = QHBoxLayout(); label2 = QLabel("선택지 2:"); self.result_label_2 = QLabel("-");
        self.result_label_2.setStyleSheet(label_style); self.result_label_2.setFixedHeight(button_size); self.result_label_2.setAlignment(Qt.AlignmentFlag.AlignCenter);
        self.select_btn_2 = QPushButton("-"); self.select_btn_2.setFixedSize(button_size, button_size); self.select_btn_2.clicked.connect(lambda: self.select_potential(1));
        hbox2.addWidget(label2); hbox2.addWidget(self.result_label_2, 1); hbox2.addWidget(self.select_btn_2); results_vbox.addLayout(hbox2)
        # 선택지 3
        hbox3 = QHBoxLayout(); label3 = QLabel("선택지 3:"); self.result_label_3 = QLabel("-");
        self.result_label_3.setStyleSheet(label_style); self.result_label_3.setFixedHeight(button_size); self.result_label_3.setAlignment(Qt.AlignmentFlag.AlignCenter);
        self.select_btn_3 = QPushButton("-"); self.select_btn_3.setFixedSize(button_size, button_size); self.select_btn_3.clicked.connect(lambda: self.select_potential(2));
        hbox3.addWidget(label3); hbox3.addWidget(self.result_label_3, 1); hbox3.addWidget(self.select_btn_3); results_vbox.addLayout(hbox3)
        main_vbox.addLayout(results_vbox)
        tracking_splitter = QSplitter(Qt.Orientation.Horizontal); not_chosen_widget = QWidget(); not_chosen_layout = QVBoxLayout(not_chosen_widget); not_chosen_layout.addWidget(QLabel("미선택 잠재력")); self.not_chosen_list = QListWidget(); not_chosen_layout.addWidget(self.not_chosen_list); chosen_widget = QWidget(); chosen_layout = QVBoxLayout(chosen_widget); chosen_layout.addWidget(QLabel("선택 완료 잠재력")); self.chosen_list = QListWidget(); chosen_layout.addWidget(self.chosen_list); tracking_splitter.addWidget(not_chosen_widget); tracking_splitter.addWidget(chosen_widget); tracking_splitter.setSizes([200, 200]);
        main_vbox.addWidget(tracking_splitter)
        self.setLayout(main_vbox);
        self.setWindowTitle('스텔라 소라 트래커 (v5.9)');
        self.setGeometry(300, 300, 500, 750);
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint);
        # 초기 덱 설정은 __init__ 마지막으로 이동

    def launch_coord_setup_from_button(self):
        QMessageBox.information(self, "알림", "지금부터 [캡처 영역 설정]을 시작합니다.\n\n2초 안에 게임의 [잠재력 선택 화면]으로 이동하세요."); self.hide(); QTimer.singleShot(2000, self.launch_coord_setup)
    def launch_coord_setup(self):
        print("launch_coord_setup 함수 실행 시작");
        try:
            print("스크린샷 시도..."); screenshot = ImageGrab.grab()
            if screenshot: print(f"스크린샷 성공: {screenshot.size}"); print("SetupWindow 생성 시도..."); self.setup_window = SetupWindow(screenshot); self.setup_window.coordinates_saved.connect(self.on_setup_complete); self.setup_window.cancelled.connect(self.on_setup_cancelled)
            else: print("스크린샷 실패 (결과가 None)"); self.show_error_message("스크린샷 캡처에 실패했습니다 (결과 없음)."); self.show()
        except Exception as e: print(f"launch_coord_setup 오류: {e}"); self.show_error_message(f"스크린샷/설정 창 생성 오류: {e}\n권한 문제나 디스플레이 설정을 확인하세요."); self.show()
    def on_setup_complete(self, coordinates):
        self.coordinates = coordinates; self.save_config(); self.load_config(); QMessageBox.information(self, "성공", "캡처 영역 설정이 'config.json' 파일에 저장되었습니다."); self.show()
    def on_setup_cancelled(self): self.show_error_message("좌표 설정이 취소되었습니다. 설정을 다시 시작하세요."); self.load_config(); self.show()
    def on_deck_changed(self, deck_name):
        print(f"덱 변경: {deck_name}"); self.current_deck_potentials = self.user_decks.get(deck_name, {}).get("potentials", []); self.chosen_potentials_in_run.clear(); self.save_config(); self.update_tracking_display()
    def reset_tracking(self):
        if QMessageBox.question(self, "확인", "현재 런의 잠재력 선택 기록을 초기화하시겠습니까?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            print("선택 기록 초기화됨."); self.chosen_potentials_in_run.clear(); self.update_tracking_display();
            label_style = "font-size: 14px; padding: 5px; color: black; border: 1px solid #ddd; background-color: #f9f9f9;"
            self.result_label_1.setText("-"); self.result_label_1.setStyleSheet(label_style); self.select_btn_1.setText("-") # 버튼 텍스트 초기화
            self.result_label_2.setText("-"); self.result_label_2.setStyleSheet(label_style); self.select_btn_2.setText("-")
            self.result_label_3.setText("-"); self.result_label_3.setStyleSheet(label_style); self.select_btn_3.setText("-")
            self.ocr_results = [None, None, None]
    def reload_decks(self):
        print("덱 데이터 새로고침 시도...");
        try:
            current_selection = self.deck_select_combo.currentText(); self.load_all_data(); self.deck_select_combo.clear();
            if self.user_decks: self.deck_select_combo.addItems(self.user_decks.keys())
            else: self.deck_select_combo.addItem("불러온 덱 없음")
            if current_selection in self.user_decks: self.deck_select_combo.setCurrentText(current_selection); self.on_deck_changed(current_selection)
            elif self.deck_select_combo.count() > 0: first_deck = self.deck_select_combo.itemText(0); self.deck_select_combo.setCurrentText(first_deck); self.on_deck_changed(first_deck)
            else: self.on_deck_changed(None)
            QMessageBox.information(self, "성공", "덱 목록을 새로고침했습니다.")
        except Exception as e: self.show_error_message(f"덱 새로고침 오류: {e}")

    def preprocess_image(self, img):
        gray_img = ImageOps.grayscale(img); threshold = 180; binary_img = gray_img.point(lambda p: 255 if p > threshold else 0); return binary_img
    
    def run_ocr_check(self):
        # (v5.8 로직 적용)
        try:
            img1_raw = ImageGrab.grab(bbox=self.coordinates['box1']); img2_raw = ImageGrab.grab(bbox=self.coordinates['box2']); img3_raw = ImageGrab.grab(bbox=self.coordinates['box3'])
            img1 = self.preprocess_image(img1_raw); img2 = self.preprocess_image(img2_raw); img3 = self.preprocess_image(img3_raw)
            tess_config = '--psm 6'
            text1_raw = pytesseract.image_to_string(img1, lang='kor', config=tess_config).strip(); text2_raw = pytesseract.image_to_string(img2, lang='kor', config=tess_config).strip(); text3_raw = pytesseract.image_to_string(img3, lang='kor', config=tess_config).strip()
        except KeyError: self.show_error_message("캡처 좌표가 설정되지 않았습니다.\n'좌표 설정 다시하기'를 눌러 설정하세요."); return
        except Exception as e: self.show_error_message(f"OCR/스크린샷 오류: {e}\n좌표가 올바른지 확인하세요 (config.json)."); return

        self.ocr_results = [None, None, None]
        buttons = [self.select_btn_1, self.select_btn_2, self.select_btn_3]
        labels = [self.result_label_1, self.result_label_2, self.result_label_3]
        texts_raw = [text1_raw, text2_raw, text3_raw]

        for i in range(3):
            matched_potential = self.update_result_label(labels[i], texts_raw[i]) # v5.7(하이라이트+원본) 사용
            if matched_potential:
                self.ocr_results[i] = matched_potential
                buttons[i].setText("OK!")
            else:
                buttons[i].setText("No!")
            # buttons[i].show() # show()는 initUI에서 이미 처리됨 (항상 보임)

    def clean_text_for_comparison(self, text):
        if not isinstance(text, str): return ""
        try: hangul_text = " ".join(re.findall(r'[가-힣]+', text)); cleaned_text = re.sub(r'\s+', '', hangul_text); return cleaned_text
        except Exception as e: print(f"clean_text_for_comparison 오류: {e} (입력: {text[:50]}...)"); return ""
    def extract_potential_name(self, deck_potential_raw):
        if not isinstance(deck_potential_raw, str): return ""
        try:
            last_bracket_index = deck_potential_raw.rfind(']');
            if last_bracket_index != -1: return deck_potential_raw[last_bracket_index + 1:].strip()
            else: return deck_potential_raw.strip()
        except Exception as e: print(f"extract_potential_name 오류: {e} (입력: {deck_potential_raw[:50]}...)"); return ""

    def update_result_label(self, label_widget, ocr_text_raw):
        # (v5.7 로직 적용 - 일치하면 하이라이트, 아니면 원본 표시)
        matched_deck_potential = None
        style_normal = "font-size: 14px; padding: 5px; color: black; border: 1px solid #ddd; background-color: #f9f9f9;"
        style_highlight = "font-size: 16px; padding: 5px; color: green; font-weight: bold; border: 1px solid #ddd; background-color: #f9f9f9;"
        style_error = "font-size: 14px; padding: 5px; color: gray; border: 1px solid #ddd; background-color: #f9f9f9;"
        style_compare_error = "font-size: 14px; padding: 5px; color: red; border: 1px solid #ddd; background-color: #f9f9f9;"

        try:
            # --- ↓↓↓ 로직 수정 시작 ↓↓↓ ---
            ocr_compare_text = self.clean_text_for_comparison(ocr_text_raw)
            is_match = False

            if ocr_compare_text:
                if isinstance(self.current_deck_potentials, list):
                    for deck_potential_raw in self.current_deck_potentials:
                        # (비교 로직은 v5.5와 동일)
                        potential_name_only = self.extract_potential_name(deck_potential_raw)
                        if not potential_name_only: continue
                        deck_compare_text = self.clean_text_for_comparison(potential_name_only)
                        if not deck_compare_text: continue
                        if ocr_compare_text == deck_compare_text: is_match = True; matched_deck_potential = deck_potential_raw; break
                        deck_words = potential_name_only.split();
                        if not deck_words: continue
                        all_words_found = True
                        for word in deck_words:
                            cleaned_word = self.clean_text_for_comparison(word)
                            if not cleaned_word: continue
                            if cleaned_word not in ocr_compare_text: all_words_found = False; break
                        if all_words_found: is_match = True; matched_deck_potential = deck_potential_raw; break
            
            # --- 결과 표시 로직 수정 ---
            if is_match:
                # 일치: DB에서 추출한 '잠재력 이름만' 표시
                clean_name = self.extract_potential_name(matched_deck_potential)
                label_widget.setText(f"★ {clean_name} ★")
                label_widget.setStyleSheet(style_highlight)
            else:
                # 불일치: OCR 원본 텍스트 표시
                display_text = ocr_text_raw if ocr_text_raw else "(인식 실패)"
                label_widget.setText(display_text)
                label_widget.setStyleSheet(style_error if not ocr_text_raw else style_normal)
            # --- ↑↑↑ 로직 수정 끝 ↑↑↑ ---

        except Exception as e:
            print(f"update_result_label 내부 오류: {e}"); label_widget.setText("(비교 오류)"); label_widget.setStyleSheet(style_compare_error); matched_deck_potential = None
        return matched_deck_potential
    
    def select_potential(self, index):
        # (v5.5와 동일)
        print(f"select_potential 슬롯 호출됨: index={index}")
        if self.ocr_results is None or not any(p is not None for p in self.ocr_results): print("선택 오류: F10으로 잠재력을 먼저 확인해야 합니다."); return
        if 0 <= index < 3 and self.ocr_results[index]:
            potential_to_add = self.ocr_results[index]
            if potential_to_add not in self.chosen_potentials_in_run: print(f"'{potential_to_add}' 선택됨. chosen 세트에 추가."); self.chosen_potentials_in_run.add(potential_to_add); self.update_tracking_display(); label_style = "font-size: 14px; padding: 5px; color: black; border: 1px solid #ddd; background-color: #f9f9f9;"; self.result_label_1.setText("-"); self.result_label_1.setStyleSheet(label_style); self.select_btn_1.setText("-"); self.result_label_2.setText("-"); self.result_label_2.setStyleSheet(label_style); self.select_btn_2.setText("-"); self.result_label_3.setText("-"); self.result_label_3.setStyleSheet(label_style); self.select_btn_3.setText("-"); self.ocr_results = [None, None, None]
            else: print(f"'{potential_to_add}'은(는) 이미 선택된 잠재력입니다.")
        else: print(f"선택 오류: 해당 선택지({index+1})는 덱에 없거나 이미 처리되었습니다 (self.ocr_results[{index}] = {self.ocr_results[index]}).")

    def update_tracking_display(self):
        # (v5.5와 동일)
        self.not_chosen_list.clear(); self.chosen_list.clear()
        if isinstance(self.current_deck_potentials, list):
            for potential in self.current_deck_potentials:
                if potential in self.chosen_potentials_in_run: self.chosen_list.addItem(QListWidgetItem(potential))
                else: self.not_chosen_list.addItem(QListWidgetItem(potential))
        print(f"추적 목록 업데이트: 미선택 {self.not_chosen_list.count()}개, 선택 {self.chosen_list.count()}개")

    def show_error_message(self, message):
        print(f"오류: {message}"); QMessageBox.warning(self, "오류", message)

if __name__ == '__main__':
    # (v5.5와 동일)
    app = QApplication(sys.argv)
    ex = TrackerApp()
    try:
        keyboard.add_hotkey('f10', lambda: ex.ocr_requested.emit())
        keyboard.add_hotkey('1', lambda: ex.selection_requested.emit(0))
        keyboard.add_hotkey('2', lambda: ex.selection_requested.emit(1))
        keyboard.add_hotkey('3', lambda: ex.selection_requested.emit(2))
        print("전역 단축키 'F10', '1', '2', '3' 설정 완료.")
        print("참고: 전역 단축키가 작동하려면 관리자 권한이 필요할 수 있습니다.")
    except Exception as e: QMessageBox.warning(ex, "경고", f"전역 단축키 설정 실패: {e}\n관리자 권한으로 실행해보세요.")
    if not ex.load_config(): print("설정 파일 없음. 설정 마법사 시작..."); ex.hide(); QTimer.singleShot(100, ex.launch_coord_setup_from_button)
    else: print("설정 파일 로드 완료. 메인 창 표시."); ex.show()
    sys.exit(app.exec())