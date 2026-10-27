package com.otterworks.fleet.portal.web;

import javax.faces.application.FacesMessage;
import javax.faces.context.FacesContext;

final class Faces {
    private Faces() { }

    static void error(String msg) {
        FacesContext.getCurrentInstance().addMessage(null, new FacesMessage(FacesMessage.SEVERITY_ERROR, msg, null));
    }

    static void info(String msg) {
        FacesContext.getCurrentInstance().addMessage(null, new FacesMessage(FacesMessage.SEVERITY_INFO, msg, null));
    }
}
