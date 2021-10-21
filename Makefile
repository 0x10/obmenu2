INSTALL_DIR=/usr/local/bin
ICON_DIR=/usr/local/share/obmenu2/


install:
	@mkdir -p $(ICON_DIR)
	@cp obmenu2.png $(ICON_DIR)
	@cp obmenu2 $(INSTALL_DIR)
