import re
import unicodedata

# Tập các ký tự tiếng Việt có dấu (hoa + thường) và chữ Đ/đ
VIE_DIACRITICS = set(
	"ÀÁẢÃẠÂẦẤẨẪẬĂẰẮẲẴẶ"
	"ÈÉẺẼẸÊỀẾỂỄỆ"
	"ÌÍỈĨỊ"
	"ÒÓỎÕỌÔỒỐỔỖỘƠỜỚỞỠỢ"
	"ÙÚỦŨỤƯỪỨỬỮỰ"
	"ỲÝỶỸỴ"
	"Đ"
	"àáảãạâầấẩẫậăằắẳẵặ"
	"èéẻẽẹêềếểễệ"
	"ìíỉĩị"
	"òóỏõọôồốổỗộơờớởỡợ"
	"ùúủũụưừứửữự"
	"ỳýỷỹỵ"
	"đ"
)

def _is_vietnamese_header(line: str) -> bool:
	"""Trả True nếu line bắt đầu bằng '##' và chứa ít nhất một ký tự tiếng Việt có dấu."""
	if not line.strip().startswith("##"):
		return False
	return any(ch in VIE_DIACRITICS for ch in line)

def _find_tomtat_index(lines):
	"""Tìm index của dòng header '## TÓM TẮT' (match khá chặt: chữ TÓM và TẮT có dấu)."""
	for i, line in enumerate(lines):
		if re.match(r'^\s*##\s*TÓM\s+TẮT\b', line.strip(), flags=re.UNICODE):
			return i
	return None

def keep_vietnamese_header_and_tomtat(text: str) -> str:
	"""
	- Tìm header đầu tiên bắt đầu bằng '##' mà chứa ký tự tiếng Việt có dấu.
	- Nếu tìm được, giữ lại header đó, chèn 1 dòng trống, rồi giữ header '## TÓM TẮT' và phần sau nó.
	- Nếu không tìm thấy header tiếng Việt nhưng có '## TÓM TẮT', thì giữ từ '## TÓM TẮT' trở đi.
	- Nếu không tìm thấy gì phù hợp thì trả về nguyên văn (strip).
	"""
	lines = text.splitlines()

	# tìm header tiếng Việt đầu tiên
	start_idx = None
	for i, line in enumerate(lines):
		if _is_vietnamese_header(line):
			start_idx = i
			break

	tom_idx = _find_tomtat_index(lines)

	# fallback: nếu không có header tiếng Việt nhưng có ## TÓM TẮT -> bắt đầu từ tom_idx
	if start_idx is None:
		if tom_idx is not None:
			return "\n".join(l.rstrip() for l in lines[tom_idx:]).strip()
		else:
			return text.strip()

	# nếu không có ## TÓM TẮT hoặc tom trước start (kỳ lạ) => giữ từ start_idx
	if tom_idx is None or tom_idx < start_idx:
		return "\n".join(l.rstrip() for l in lines[start_idx:]).strip()

	# trường hợp bình thường: start_idx <= tom_idx
	# giữ header start, một dòng trống, header TÓM TẮT, rồi phần còn lại (sau tom_idx)
	result = []
	result.append(lines[start_idx].strip())
	if tom_idx != start_idx:
		result.append("")  # bắt buộc 1 dòng trống giữa 2 header
		result.append(lines[tom_idx].strip())
		# thêm phần sau '## TÓM TẮT' (giữ nguyên spacing trên các dòng phía sau)
		if tom_idx + 1 < len(lines):
			rest = [l.rstrip() for l in lines[tom_idx+1:]]
			# nếu phần sau bắt đầu bằng dòng rỗng, giữ nguyên (không ép)
			result.extend(rest)
	else:
		# trường hợp header tìm thấy chính là '## TÓM TẮT'
		result.extend([l.rstrip() for l in lines[start_idx+1:]])

	return "\n".join(result).rstrip()


def normalize_unicode_artifacts(text: str) -> str:
	"""
	Chuẩn hoá các lỗi dạng '/uniXXXX' trong text.
	Nếu có ký tự ngay sau '/uniXXXX' (ví dụ 'kh/uni1ECFe'),
	thì bỏ ký tự đó và chỉ giữ lại ký tự Unicode đúng.
	"""
	# Bắt cả cụm '/uniXXXX' + optional chữ cái đi kèm ngay sau
	pattern = re.compile(r'/uni([0-9A-Fa-f]{4})([a-zA-Z])?')

	def _repl(m):
		code_hex = m.group(1)
		codepoint = int(code_hex, 16)
		try:
			return chr(codepoint)  # chỉ giữ ký tự Unicode, bỏ ký tự thừa sau
		except Exception:
			return m.group(0)

	text = pattern.sub(_repl, text)

	# Normalize NFC để tổ hợp dấu đầy đủ
	text = unicodedata.normalize("NFC", text)

	return text.strip()


def remove_tail_sections(text: str) -> str:
	"""
	Loại bỏ phần từ '## LỜI CẢM ƠN' nếu có.
	Nếu không có thì fallback sang '## TÀI LIỆU THAM KHẢO'.
	"""
	# Regex cho các header
	ack_pattern = re.compile(
		r"^##\s*L\s*Ờ\s*I\s*C\s*Ả\s*M\s*Ơ\s*N.*",
		re.IGNORECASE | re.MULTILINE
	)
	ref_pattern = re.compile(
		r"^##\s*T\s*À\s*I\s*L\s*I\s*Ệ\s*U\s*T\s*H\s*A\s*M\s*K\s*H\s*Ả\s*O.*",
		re.IGNORECASE | re.MULTILINE
	)

	# Ưu tiên tìm 'LỜI CẢM ƠN'
	match_ack = ack_pattern.search(text)
	if match_ack:
		return text[:match_ack.start()].rstrip()

	# Nếu không có thì fallback sang 'TÀI LIỆU THAM KHẢO'
	match_ref = ref_pattern.search(text)
	if match_ref:
		return text[:match_ref.start()].rstrip()

	# Nếu không tìm thấy gì thì trả về nguyên văn
	return text

def remove_noise(text: str) -> str:
	"""
	Loại bỏ các text nhiễu:
	- Dòng bắt đầu bằng 'Hình X.'
	- Các block <!-- ... -->
	"""
	# Xóa dòng bắt đầu bằng "Hình <số>."
	text = re.sub(r"^Hình\s*\d+\..*$", "", text, flags=re.MULTILINE)

	# Xóa toàn bộ comment <!-- ... -->
	text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)

	# Xóa dòng trống thừa sau khi loại bỏ
	text = re.sub(r"\n\s*\n", "\n\n", text)

	return text.strip()


def remove_ocr_footnotes(text: str) -> str:
	return re.sub(r"^\s*\d+\s+[A-ZÀ-Ỹ].*$", "", text, flags=re.MULTILINE)


def normalize_markdown_pipeline(text: str) -> str:
	text = normalize_unicode_artifacts(text)
	text = keep_vietnamese_header_and_tomtat(text)
	text = remove_tail_sections(text)
	text = remove_noise(text)
	text = remove_ocr_footnotes(text)
	return text