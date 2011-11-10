# file: build-osx-common.make

SRC             = avl.c avlmodule.c
OBJ             = $(SRC:%.c=$(OBJ_DIR)/%.o)
LIB             = $(LIB_DIR)/avl.so

build: init $(LIB)

init:
	@[ -d $(OBJ_DIR) ] || mkdir -p $(OBJ_DIR)
	@[ -d $(LIB_DIR) ] || mkdir -p $(LIB_DIR)

$(LIB): $(OBJ)
	cc -bundle $(LINK_FLAGS) $(OBJ) -o $@
	@echo _initavl >.xsym
	nmedit -s .xsym $@ && strip -x $@
	@rm .xsym

$(OBJ): $(OBJ_DIR)/%.o: %.c
	cc -c $(CFLAGS) $(OTHER_CFLAGS) $(DEFS) -I$(PYTHON_INCL) $< -o $@

install: build
	cp -f $(LIB) $(PYTHON_EXTDIR)

clean: 
	rm -f $(OBJ) 
	rm -f .xsym

topclean: clean
	rm -rf $(LIB_DIR)
	if [ -d $(OBJ_DIR) ] && [ -z "`ls -l $(OBJ_DIR) | cut -c1`" ]; then rmdir $(OBJ_DIR); fi

# depend: $(MAKEFILE) $(SRC)
# 	makedepend -I$(PYTHON_INCL) -f $(MAKEFILE) $(SRC)
