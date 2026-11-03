package com.otterworks.ottershops.account;

import com.otterworks.ottershops.auth.CurrentCustomer;
import com.otterworks.ottershops.common.ApiException;
import jakarta.servlet.http.HttpServletRequest;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;
import java.util.UUID;

@RestController
@RequestMapping("/api/account/addresses")
public class AddressController {
    private final AddressService addresses;
    private final CurrentCustomer current;

    public AddressController(AddressService addresses, CurrentCustomer current) {
        this.addresses = addresses;
        this.current = current;
    }

    private UUID me(HttpServletRequest req) {
        return current.id(req).orElseThrow(ApiException::unauthorized);
    }

    @GetMapping
    public List<AddressService.Address> list(HttpServletRequest req) {
        return addresses.list(me(req));
    }

    @PostMapping
    public List<AddressService.Address> add(@RequestBody AddressService.Input body, HttpServletRequest req) {
        return addresses.add(me(req), body);
    }

    @PostMapping("/{id}/default")
    public List<AddressService.Address> makeDefault(@PathVariable UUID id, HttpServletRequest req) {
        return addresses.makeDefault(me(req), id);
    }

    @DeleteMapping("/{id}")
    public List<AddressService.Address> delete(@PathVariable UUID id, HttpServletRequest req) {
        return addresses.delete(me(req), id);
    }
}
