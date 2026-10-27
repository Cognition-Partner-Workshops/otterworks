package com.otterworks.fleet.portal.model;

import java.io.Serializable;
import java.math.BigDecimal;
import java.util.Date;
import javax.persistence.*;

@Entity
@Table(name = "vehicle")
public class Vehicle implements Serializable {
    @Id @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    private String plate;
    private String make;
    private String model;
    @Column(name = "list_price") private BigDecimal listPrice;
    @Column(name = "co2_g_km") private Integer co2;
    @Column(columnDefinition = "bpchar") private String fuel;
    @Temporal(TemporalType.DATE) @Column(name = "registered_on") private Date registeredOn;
    @ManyToOne @JoinColumn(name = "owner_employee_id") private Employee owner;

    public Long getId() { return id; }
    public String getPlate() { return plate; }
    public void setPlate(String plate) { this.plate = plate; }
    public String getMake() { return make; }
    public void setMake(String make) { this.make = make; }
    public String getModel() { return model; }
    public void setModel(String model) { this.model = model; }
    public BigDecimal getListPrice() { return listPrice; }
    public void setListPrice(BigDecimal listPrice) { this.listPrice = listPrice; }
    public Integer getCo2() { return co2; }
    public void setCo2(Integer co2) { this.co2 = co2; }
    public String getFuel() { return fuel; }
    public void setFuel(String fuel) { this.fuel = fuel; }
    public Date getRegisteredOn() { return registeredOn; }
    public void setRegisteredOn(Date registeredOn) { this.registeredOn = registeredOn; }
    public Employee getOwner() { return owner; }
    public void setOwner(Employee owner) { this.owner = owner; }
    public String getLabel() { return plate + "  " + make + " " + model; }
}
