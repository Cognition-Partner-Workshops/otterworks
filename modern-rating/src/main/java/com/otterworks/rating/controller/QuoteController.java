package com.otterworks.rating.controller;

import com.otterworks.rating.dto.QuoteForm;
import com.otterworks.rating.model.Quote;
import com.otterworks.rating.service.RatingService;
import jakarta.validation.Valid;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Controller;
import org.springframework.ui.Model;
import org.springframework.validation.BindingResult;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.ResponseBody;

@Controller
public class QuoteController {

    private final RatingService rating;

    public QuoteController(RatingService rating) {
        this.rating = rating;
    }

    @GetMapping("/")
    public String page(Model model) {
        model.addAttribute("form", QuoteForm.example());
        return "quote";
    }

    @PostMapping("/")
    public String quote(@Valid QuoteForm form, BindingResult errors, Model model) {
        model.addAttribute("form", form);
        if (!errors.hasErrors()) {
            model.addAttribute("quote", rating.rate(form.toPolicy()));
        }
        return "quote";
    }

    @PostMapping("/api/quotes")
    @ResponseBody
    public ResponseEntity<Quote> api(@Valid @RequestBody QuoteForm form) {
        return ResponseEntity.ok(rating.rate(form.toPolicy()));
    }
}
