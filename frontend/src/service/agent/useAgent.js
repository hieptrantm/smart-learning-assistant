"use client";

import { useCallback } from "react";
import { getTokensInfo } from "../auth/token";

// data = {detected_ingredients: []}
export function useStartAgentService() {
    return useCallback(async (data) => {
        const tokens = getTokensInfo();

        const headers = new Headers();
        headers.set("Content-Type", "application/json");

        if (tokens?.token) {
            headers.set("Authorization", `Bearer ${tokens.token}`);
        }

        const res = await fetch(`/agent/start`, {
            method: "POST",
            headers,
            body: JSON.stringify(data), 
        });
        
        if (!res.ok) {
            const errorText = await res.text();
            throw new Error(`Start agent failed: ${res.status} - ${errorText}`);
        }

        return res.json();
    }, []); 
}