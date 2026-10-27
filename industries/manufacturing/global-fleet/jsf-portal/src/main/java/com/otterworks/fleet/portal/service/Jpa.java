package com.otterworks.fleet.portal.service;

import java.util.HashMap;
import java.util.Map;
import javax.persistence.EntityManager;
import javax.persistence.EntityManagerFactory;
import javax.persistence.Persistence;

public final class Jpa {
    private static volatile EntityManagerFactory emf;

    private Jpa() { }

    public static EntityManager em() {
        if (emf == null) {
            synchronized (Jpa.class) {
                if (emf == null) {
                    Map<String, String> p = new HashMap<String, String>();
                    p.put("javax.persistence.jdbc.url", env("DB_URL", "jdbc:postgresql://localhost:5432/fleet"));
                    p.put("javax.persistence.jdbc.user", env("DB_USER", "fleet"));
                    p.put("javax.persistence.jdbc.password", env("DB_PASSWORD", ""));
                    emf = Persistence.createEntityManagerFactory("fleet", p);
                }
            }
        }
        return emf.createEntityManager();
    }

    private static String env(String k, String d) {
        String v = System.getenv(k);
        return v == null || v.isEmpty() ? d : v;
    }
}
