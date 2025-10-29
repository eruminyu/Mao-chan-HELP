# tracker.py (v4.10 - 비교 로직 상세 수정)
import sys
import json
import os
import time
import re
import pygetwindow as gw
import pytesseract
from PIL import Image, ImageGrab, ImageOps
from PIL.ImageQt import ImageQt
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
                             QPushButton, QLabel, QComboBox, QFormLayout,
                             QMessageBox, QListWidget, QListWidgetItem, QDialog)
from PyQt6.QtCore import Qt, QTimer, QRect, pyqtSignal, QPoint, QRectF
from PyQt6.QtGui import QPixmap, QPainter, QFont, QColor, QBrush, QPen

# --- 경로 설정 함수 ---
# (v4.9와 동일)
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
# (v4.9와 동일)
YOUR_TESSERACT_PATH = get_bundled_path(os.path.join('tesseract_bundle', 'tesseract.exe'))
CONFIG_FILE = get_datafile_path('config.json')
GAMEDATA_FILE = get_datafile_path('gamedata.json')
USERDECKS_FILE = get_datafile_path('user_decks.json')

# --- Tesseract 검사 ---
# (v4.9와 동일)
try:
    pytesseract.pytesseract.tesseract_cmd = YOUR_TESSERACT_PATH
    pytesseract.get_tesseract_version()
except Exception as e:
    app_temp = QApplication(sys.argv); QMessageBox.critical(None, "치명적 오류", f"Tesseract 초기화 오류: {e}\ntesseract_bundle 폴더나 경로를 확인하세요."); sys.exit()
# --------------------

# --- 1단계 GameWindowSetupDialog 클래스 제거됨 ---

# --- 2단계 SetupWindow 클래스 ---
# (v4.9와 동일)
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
            if screen: screen_geometry = screen.geometry(); screen_center_x = screen_geometry.width() // 2; screen_center_y = screen_geometry.height() // 2
            else: screen_center_x = self.width() // 2; screen_center_y = self.height() // 2
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
    # (v4.9와 동일)
    def __init__(self): super().__init__(); self.game_data = {}; self.user_decks = {}; self.coordinates = {}; self.setup_window = None; self.load_all_data(); self.initUI()
    def load_all_data(self):
        try:
            with open(GAMEDATA_FILE, 'r', encoding='utf-8') as f: self.game_data = json.load(f)
            with open(USERDECKS_FILE, 'r', encoding='utf-8') as f: self.user_decks = json.load(f)
        except FileNotFoundError as e: self.show_error_message(f"데이터 파일({e.filename})을 찾을 수 없습니다.")
        except Exception as e: self.show_error_message(f"데이터 로드 오류: {e}")
    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f: config_data = json.load(f)
                self.coordinates = config_data.get("coordinates", {});
                if 'box1' in self.coordinates and 'box2' in self.coordinates and 'box3' in self.coordinates: print(f"좌표 로드 성공: {self.coordinates}"); self.run_button.setEnabled(True); self.config_status_label.setText("상태: 좌표 설정 완료"); self.config_status_label.setStyleSheet("color: green;"); return True
                else: raise ValueError("좌표 데이터가 불완전합니다.")
            except Exception as e: self.show_error_message(f"config.json 읽기 오류: {e}\n설정을 다시 진행합니다.")
        self.run_button.setEnabled(False); self.config_status_label.setText("상태: 캡처 영역 설정 필요"); self.config_status_label.setStyleSheet("color: red;"); return False
    def initUI(self):
        deck_select_layout = QHBoxLayout(); self.deck_select_label = QLabel("적용할 덱:"); self.deck_select_combo = QComboBox(self);
        if self.user_decks: self.deck_select_combo.addItems(self.user_decks.keys())
        else: self.deck_select_combo.addItem("불러온 덱 없음")
        self.deck_select_combo.textActivated.connect(self.on_deck_changed); deck_select_layout.addWidget(self.deck_select_label); deck_select_layout.addWidget(self.deck_select_combo); self.run_button = QPushButton("현재 잠재력 확인 (F10)", self); self.run_button.setShortcut("F10"); self.run_button.clicked.connect(self.run_ocr_check); self.run_button.setStyleSheet("font-size: 16px; padding: 10px;"); self.setup_button = QPushButton("좌표 설정 다시하기", self); self.setup_button.clicked.connect(self.launch_coord_setup_from_button); self.config_status_label = QLabel("상태: 로딩 중..."); setup_layout = QHBoxLayout(); setup_layout.addWidget(self.setup_button); setup_layout.addWidget(self.config_status_label); self.result_layout = QFormLayout(); self.result_label_1 = QLabel("..."); self.result_label_2 = QLabel("..."); self.result_label_3 = QLabel("..."); self.result_label_1.setStyleSheet("font-size: 14px; padding: 5px;"); self.result_label_2.setStyleSheet("font-size: 14px; padding: 5px;"); self.result_label_3.setStyleSheet("font-size: 14px; padding: 5px;"); self.result_layout.addRow(QLabel("선택지 1:"), self.result_label_1); self.result_layout.addRow(QLabel("선택지 2:"), self.result_label_2); self.result_layout.addRow(QLabel("선택지 3:"), self.result_label_3); vbox = QVBoxLayout(); vbox.addLayout(deck_select_layout); vbox.addWidget(self.run_button); vbox.addLayout(setup_layout); vbox.addLayout(self.result_layout); self.setLayout(vbox); self.setWindowTitle('스텔라 소라 트래커 (v4.10 - 최종 비교 수정)'); self.setGeometry(300, 300, 400, 300); self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint);
        if self.deck_select_combo.count() > 0: self.on_deck_changed(self.deck_select_combo.currentText())
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
        self.coordinates = coordinates; config_data = {"coordinates": self.coordinates}
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f: json.dump(config_data, f, indent=2)
            self.load_config(); QMessageBox.information(self, "성공", "캡처 영역 설정이 'config.json' 파일에 저장되었습니다.")
        except Exception as e: self.show_error_message(f"config.json 저장 실패: {e}")
        self.show()
    def on_setup_cancelled(self): self.show_error_message("좌표 설정이 취소되었습니다. 설정을 다시 시작하세요."); self.load_config(); self.show()
    def on_deck_changed(self, deck_name): self.current_deck_potentials = self.user_decks.get(deck_name, {}).get("potentials", [])
    def preprocess_image(self, img):
        gray_img = ImageOps.grayscale(img); threshold = 180; binary_img = gray_img.point(lambda p: 255 if p > threshold else 0); return binary_img

    # --- (★수정된 부분★) ---
    def run_ocr_check(self):
        try:
            img1_raw = ImageGrab.grab(bbox=self.coordinates['box1']); img2_raw = ImageGrab.grab(bbox=self.coordinates['box2']); img3_raw = ImageGrab.grab(bbox=self.coordinates['box3'])
            img1 = self.preprocess_image(img1_raw); img2 = self.preprocess_image(img2_raw); img3 = self.preprocess_image(img3_raw)
            tess_config = '--psm 6'
            text1_raw = pytesseract.image_to_string(img1, lang='kor', config=tess_config).strip(); text2_raw = pytesseract.image_to_string(img2, lang='kor', config=tess_config).strip(); text3_raw = pytesseract.image_to_string(img3, lang='kor', config=tess_config).strip()
            
            # (수정) 여기서 한글만 필터링하지 않음 - 비교 함수에서 처리
            # text1_kor = ... (제거)

        except KeyError: self.show_error_message("캡처 좌표가 설정되지 않았습니다.\n'좌표 설정 다시하기'를 눌러 설정하세요."); return
        except Exception as e: self.show_error_message(f"OCR/스크린샷 오류: {e}\n좌표가 올바른지 확인하세요 (config.json)."); return
        
        # update_result_label 호출 시 원본 텍스트만 전달
        self.update_result_label(self.result_label_1, text1_raw)
        self.update_result_label(self.result_label_2, text2_raw)
        self.update_result_label(self.result_label_3, text3_raw)

    def clean_text_for_comparison(self, text):
        """비교를 위해 텍스트에서 한글+공백 외 모든 문자 제거 + 공백 제거"""
        if not isinstance(text, str): return ""
        try:
            # 1. 한글과 공백만 남기기
            hangul_text = " ".join(re.findall(r'[가-힣]+', text))
            # 2. 남은 공백 제거
            cleaned_text = re.sub(r'\s+', '', hangul_text)
            return cleaned_text
        except Exception as e:
            print(f"clean_text_for_comparison 오류: {e} (입력: {text[:50]}...)")
            return ""

    def extract_potential_name(self, deck_potential_raw):
        # (v4.9와 동일)
        if not isinstance(deck_potential_raw, str): return ""
        try:
            last_bracket_index = deck_potential_raw.rfind(']');
            if last_bracket_index != -1: return deck_potential_raw[last_bracket_index + 1:].strip()
            else: return deck_potential_raw.strip()
        except Exception as e: print(f"extract_potential_name 오류: {e} (입력: {deck_potential_raw[:50]}...)"); return ""

    def update_result_label(self, label_widget, ocr_text_raw):
        """GUI 레이블 업데이트 (비교 로직 수정)"""
        try:
            # 원본 텍스트 표시 (게임 실행 여부 등 특수 상태 처리 제거)
            label_widget.setText(ocr_text_raw)
            label_widget.setStyleSheet("font-size: 14px; padding: 5px; color: black;") # 기본 스타일

            # 비교용 OCR 텍스트 (한글+공백만 남기고 공백 제거)
            ocr_compare_text = self.clean_text_for_comparison(ocr_text_raw)

            if not ocr_compare_text: # 비교할 한글이 없으면 하이라이트 불가
                 label_widget.setText(ocr_text_raw or "(인식 실패)") # 원본 표시
                 label_widget.setStyleSheet("font-size: 14px; padding: 5px; color: gray;")
                 return

            is_match = False
            if isinstance(self.current_deck_potentials, list):
                for deck_potential_raw in self.current_deck_potentials:
                    # 덱에서 이름 추출
                    potential_name_only = self.extract_potential_name(deck_potential_raw)
                    if not potential_name_only: continue

                    # 비교용 덱 이름 (한글+공백만 남기고 공백 제거)
                    deck_compare_text = self.clean_text_for_comparison(potential_name_only)
                    if not deck_compare_text: continue

                    # --- 조건 1: 완전 일치 (정제된 이름 기준) ---
                    if ocr_compare_text == deck_compare_text:
                        is_match = True
                        break

                    # --- 조건 2: 단어 단위 일치 (원본 이름 기준) ---
                    deck_words = potential_name_only.split() # 원본 이름에서 공백으로 단어 분리
                    if not deck_words: continue # 분리된 단어 없으면 스킵

                    all_words_found = True
                    for word in deck_words:
                        cleaned_word = self.clean_text_for_comparison(word) # 각 단어도 정제
                        if not cleaned_word: continue # 정제 후 빈 단어 스킵

                        # 정제된 단어가 정제된 OCR 텍스트에 포함되지 않으면 실패
                        if cleaned_word not in ocr_compare_text:
                            all_words_found = False
                            break # 내부 루프 탈출
                    
                    if all_words_found: # 모든 단어가 포함되었으면
                        is_match = True
                        break # 외부 루프 탈출

            # 최종 결과 표시
            if is_match:
                label_widget.setText(f"★ {ocr_text_raw} ★")
                label_widget.setStyleSheet("font-size: 16px; padding: 5px; color: green; font-weight: bold;")
            # else: # 불일치 시 기본 스타일 유지 (위에서 이미 설정됨)
            #     pass 

        except Exception as e:
            print(f"update_result_label 내부 오류: {e}")
            label_widget.setText("(비교 오류)"); label_widget.setStyleSheet("font-size: 14px; padding: 5px; color: red;")
    # ------------------------

    def show_error_message(self, message):
        print(f"오류: {message}"); QMessageBox.warning(self, "오류", message)

if __name__ == '__main__':
    # (v4.9와 동일)
    app = QApplication(sys.argv)
    ex = TrackerApp()
    if not ex.load_config(): print("설정 파일 없음. 설정 마법사 시작..."); ex.hide(); QTimer.singleShot(100, ex.launch_coord_setup_from_button) 
    else: print("설정 파일 로드 완료. 메인 창 표시."); ex.show()
    sys.exit(app.exec())