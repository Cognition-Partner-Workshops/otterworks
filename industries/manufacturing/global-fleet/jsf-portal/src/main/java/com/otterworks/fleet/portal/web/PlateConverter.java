package com.otterworks.fleet.portal.web;

import javax.faces.component.UIComponent;
import javax.faces.context.FacesContext;
import javax.faces.convert.Converter;
import javax.faces.convert.FacesConverter;

@FacesConverter("plateConverter")
public class PlateConverter implements Converter {

    @Override
    public Object getAsObject(FacesContext ctx, UIComponent component, String value) {
        if (value == null) {
            return null;
        }
        String v = value.trim().replaceAll("\\s+", " ").toUpperCase();
        return v.isEmpty() ? null : v;
    }

    @Override
    public String getAsString(FacesContext ctx, UIComponent component, Object value) {
        return value == null ? "" : value.toString();
    }
}
