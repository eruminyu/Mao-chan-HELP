# Mao-chan_Helper.py
import sys
import os
import keyboard
import pytesseract
from PyQt6.QtWidgets import (QApplication, QMainWindow, QTabWidget, QMessageBox)
from PyQt6.QtCore import QTimer

from tracker import TrackerApp
from editor import DBEditorApp

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('마오 도우미 (v7.0)')
        self.setGeometry(100, 100, 520, 900)

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        # 에디터와 트래커 인스턴스 생성
        # 트래커가 먼저 생성되어야 단축키 설정 등을 불러올 수 있습니다.
        self.tracker_widget = TrackerApp()
        self.editor_widget = DBEditorApp()

        # 탭에 위젯 추가
        self.tabs.addTab(self.tracker_widget, "트래커")
        self.tabs.addTab(self.editor_widget, "에디터")

        # 시그널 연결: 에디터에서 저장하면 트래커가 데이터 리로드
        self.editor_widget.data_saved.connect(self.tracker_widget.reload_all_data_and_decks)

def main():
    app = QApplication(sys.argv)

    # Tesseract 초기화
    try:
        # tracker.py에서 가져온 경로 설정 함수
        def get_bundled_path(relative_path):
            try: base_path = sys._MEIPASS
            except Exception: base_path = os.path.abspath(".")
            return os.path.join(base_path, relative_path)
        
        YOUR_TESSERACT_PATH = get_bundled_path(os.path.join('tesseract_bundle', 'tesseract.exe'))
        pytesseract.pytesseract.tesseract_cmd = YOUR_TESSERACT_PATH
        pytesseract.get_tesseract_version()
        print("Tesseract 초기화 완료.")
    except Exception as e:
        QMessageBox.critical(None, "치명적 오류", f"Tesseract 초기화 오류: {e}\n\nTesseract가 설치되지 않았거나 경로가 잘못되었습니다.\n프로그램을 종료합니다.")
        sys.exit()

    main_window = MainWindow()

    # 트래커의 전역 단축키 설정 로직 가져오기
    ex = main_window.tracker_widget
    try:
        if ex.hotkeys.get("ocr"): keyboard.add_hotkey(ex.hotkeys["ocr"], ex.ocr_requested.emit)
        if ex.hotkeys.get("select1"): keyboard.add_hotkey(ex.hotkeys["select1"], lambda: ex.selection_requested.emit(0))
        if ex.hotkeys.get("select2"): keyboard.add_hotkey(ex.hotkeys["select2"], lambda: ex.selection_requested.emit(1))
        if ex.hotkeys.get("select3"): keyboard.add_hotkey(ex.hotkeys["select3"], lambda: ex.selection_requested.emit(2))
        print("전역 단축키 설정 완료.")
    except Exception as e:
        QMessageBox.warning(main_window, "경고", f"전역 단축키 설정 실패: {e}\n관리자 권한으로 실행해보세요.")

    main_window.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()