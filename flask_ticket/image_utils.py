import cv2


def preprocess(path):
    """
    Prétraitement d'une image de ticket de caisse :
    - Passage en niveaux de gris
    - Augmentation du contraste
    - Flou léger pour réduire le bruit
    - Redimensionnement si largeur > 800px
    Accepte un chemin (str) ou un array numpy (BGR ou GRAY)
    Retourne l'image prétraitée (numpy array)
    """
    if isinstance(path, str):
        img = cv2.imread(path)
        if img is None:
            raise ValueError(f"Impossible de lire l'image : {path}")
    else:
        img = path
    cropped = auto_crop_ticket(img)
    # Resize à 600px de large max
    h, w = cropped.shape[:2]
    if w > 600:
        ratio = 600 / w
        cropped = cv2.resize(cropped, (600, int(h * ratio)))
    return cropped

def auto_crop_ticket(image):
    import numpy as np
    # 1. grayscale
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    # 2. blur léger (utile pour contours)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    # 3. détection des bords
    edges = cv2.Canny(blur, 50, 150)
    # 4. trouver les contours
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return image  # fallback
    # 5. plus grand contour = candidat ticket
    largest = max(contours, key=cv2.contourArea)
    img_area = image.shape[0] * image.shape[1]
    area = cv2.contourArea(largest)
    # Si le contour est trop petit (<20% de l'image), on ne crop pas
    if area < 0.2 * img_area:
        return image
    # 6. approx polygon (on cherche un rectangle)
    peri = cv2.arcLength(largest, True)
    approx = cv2.approxPolyDP(largest, 0.02 * peri, True)
    if len(approx) == 4:
        pts = approx.reshape(4, 2)
        rect = order_points(pts)
        (tl, tr, br, bl) = rect
        widthA = np.linalg.norm(br - bl)
        widthB = np.linalg.norm(tr - tl)
        maxWidth = int(max(widthA, widthB))
        heightA = np.linalg.norm(tr - br)
        heightB = np.linalg.norm(tl - bl)
        maxHeight = int(max(heightA, heightB))
        dst = np.array([
            [0, 0],
            [maxWidth - 1, 0],
            [maxWidth - 1, maxHeight - 1],
            [0, maxHeight - 1]
        ], dtype="float32")
        M = cv2.getPerspectiveTransform(rect, dst)
        warped = cv2.warpPerspective(image, M, (maxWidth, maxHeight))
        return warped
    # fallback si pas rectangle
    x, y, w, h = cv2.boundingRect(largest)
    # Si le rectangle est trop petit, on ne crop pas
    if w * h < 0.2 * img_area:
        return image
    return image[y:y+h, x:x+w]

def order_points(pts):
    import numpy as np
    rect = np.zeros((4, 2), dtype="float32")
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]  # top-left
    rect[2] = pts[np.argmax(s)]  # bottom-right
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]  # top-right
    rect[3] = pts[np.argmax(diff)]  # bottom-left
    return rect
