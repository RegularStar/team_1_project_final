document.addEventListener('DOMContentLoaded', () => {
  const input = document.querySelector('#post-image');
  const nameLabel = document.querySelector('[data-role="image-name"]');
  if (!input || !nameLabel) return;

  const previewImg = document.querySelector('[data-role="image-preview"]');
  const previewContainer = document.querySelector('.image-upload__preview');
  const placeholder = document.querySelector('[data-role="image-placeholder"]');
  const removeCheckbox = document.querySelector('#remove-image');

  const defaultName = nameLabel.dataset.default || '파일이 선택되지 않았습니다.';
  const originalName = nameLabel.dataset.original || '';
  const originalSrc = previewImg ? previewImg.dataset.original || '' : '';
  const placeholderDefault = placeholder ? (placeholder.dataset.default || placeholder.textContent || '') : '';

  const showPlaceholder = (message) => {
    if (placeholder) {
      placeholder.hidden = false;
      placeholder.textContent = message || placeholderDefault;
    }
    if (previewContainer) {
      previewContainer.classList.remove('image-upload__preview--active');
    }
  };

  const hidePlaceholder = () => {
    if (placeholder) {
      placeholder.hidden = true;
      placeholder.textContent = placeholderDefault;
    }
    if (previewContainer) {
      previewContainer.classList.add('image-upload__preview--active');
    }
  };

  const resetToOriginal = () => {
    if (originalName) {
      nameLabel.textContent = originalName;
    } else {
      nameLabel.textContent = defaultName;
    }

    if (previewImg) {
      if (originalSrc) {
        previewImg.src = originalSrc;
        previewImg.hidden = false;
        hidePlaceholder();
      } else {
        previewImg.hidden = true;
        showPlaceholder();
      }
    } else if (placeholder) {
      showPlaceholder();
    }
  };

  const markAsRemoved = () => {
    nameLabel.textContent = '이미지가 삭제될 예정입니다.';
    if (previewImg) {
      previewImg.hidden = true;
    }
    showPlaceholder('이미지가 삭제될 예정입니다.');
  };

  const initializePreviewState = () => {
    if (previewImg && !previewImg.hidden && previewImg.src) {
      hidePlaceholder();
    } else {
      showPlaceholder();
    }

    if (removeCheckbox && removeCheckbox.checked) {
      markAsRemoved();
    }
  };

  const handleFileSelection = () => {
    if (input.files && input.files.length > 0) {
      const file = input.files[0];
      nameLabel.textContent = file.name;

      if (previewImg) {
        const reader = new FileReader();
        reader.onload = (event) => {
          const result = event.target && event.target.result ? event.target.result : '';
          previewImg.src = result;
          previewImg.hidden = !result;
          if (result) {
            hidePlaceholder();
          } else {
            showPlaceholder();
          }
        };
        reader.readAsDataURL(file);
      } else {
        hidePlaceholder();
      }

      if (removeCheckbox) {
        removeCheckbox.checked = false;
      }
    } else {
      if (removeCheckbox && removeCheckbox.checked) {
        markAsRemoved();
      } else {
        resetToOriginal();
      }
    }
  };

  initializePreviewState();

  input.addEventListener('change', handleFileSelection);

  if (removeCheckbox) {
    removeCheckbox.addEventListener('change', () => {
      if (removeCheckbox.checked) {
        input.value = '';
        markAsRemoved();
      } else {
        resetToOriginal();
      }
    });
  }
});
