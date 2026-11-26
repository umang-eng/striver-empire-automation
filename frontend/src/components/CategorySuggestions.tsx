"use client";

import { ChevronDown, ChevronUp, Search } from "lucide-react";
import { useMemo, useState } from "react";
import { CategoryGroup } from "@/lib/types";
import { SuggestionCard } from "./SuggestionCard";

interface CategorySuggestionsProps {
  groups: CategoryGroup[];
  onUseTemplate: (template: string) => void;
}

export function CategorySuggestions({ groups, onUseTemplate }: CategorySuggestionsProps) {
  const [activeTab, setActiveTab] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [showSubcategories, setShowSubcategories] = useState(true);

  const tabs = useMemo(
    () => [
      { id: "all", label: "All Categories" },
      ...groups.map((g) => ({ id: g.id, label: g.label })),
    ],
    [groups]
  );

  const filteredGroups = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    return groups
      .filter((g) => activeTab === "all" || g.id === activeTab)
      .map((g) => {
        const mainTemplates = q
          ? g.main_templates.filter(
              (t) => t.toLowerCase().includes(q) || g.label.toLowerCase().includes(q)
            )
          : g.main_templates;
        const subcategories = q
          ? g.subcategories.filter(
              (s) =>
                s.template.toLowerCase().includes(q) ||
                s.name.toLowerCase().includes(q) ||
                g.label.toLowerCase().includes(q)
            )
          : g.subcategories;
        return { ...g, mainTemplates, subcategories };
      })
      .filter((g) => g.mainTemplates.length > 0 || g.subcategories.length > 0);
  }, [groups, activeTab, searchQuery]);

  return (
    <aside
      aria-label="Category message suggestions"
      className="rounded-3xl border border-white/18 bg-white/[0.06] p-4 sm:p-5 backdrop-blur-2xl shadow-[inset_0_1px_0_rgba(255,255,255,0.2),0_20px_50px_rgba(0,0,0,0.4)] flex flex-col gap-3.5"
    >
      <div className="flex items-center justify-between gap-2">
        <div>
          <h2 className="text-sm font-semibold text-white">Category Suggestions</h2>
          <p className="text-[11px] text-white/55">
            Click a template to insert &amp; customize discount, or copy it.
          </p>
        </div>
        <button
          type="button"
          onClick={() => setShowSubcategories((prev) => !prev)}
          className="inline-flex items-center gap-1 rounded-full border border-white/15 bg-white/[0.07] px-2.5 py-1 text-[11px] font-medium text-white/80 hover:bg-white/15 transition-colors cursor-pointer"
        >
          <span>{showSubcategories ? "Compact" : "Show Subs"}</span>
          {showSubcategories ? (
            <ChevronUp className="h-3 w-3" aria-hidden="true" />
          ) : (
            <ChevronDown className="h-3 w-3" aria-hidden="true" />
          )}
        </button>
      </div>

      {/* Search input */}
      <div className="relative">
        <Search
          className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-white/45"
          aria-hidden="true"
        />
        <input
          type="search"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="Filter categories (e.g. shirt, jeans, winter)..."
          aria-label="Filter category suggestions"
          className="w-full rounded-xl border border-white/12 bg-black/25 pl-8 pr-3 py-2 text-xs text-white placeholder:text-white/40 focus:border-white/30 focus:outline-none"
        />
      </div>

      {/* Category tabs */}
      <div className="flex items-center gap-1.5 overflow-x-auto pb-1 no-scrollbar" role="tablist">
        {tabs.map((tab) => {
          const active = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              role="tab"
              aria-selected={active}
              type="button"
              onClick={() => setActiveTab(tab.id)}
              className={`shrink-0 rounded-full px-3 py-1 text-[11px] font-medium transition-all cursor-pointer ${
                active
                  ? "bg-white text-neutral-950 shadow-sm"
                  : "border border-white/12 bg-white/[0.05] text-white/75 hover:bg-white/12 hover:text-white"
              }`}
            >
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* Scrollable suggestion groups */}
      <div className="max-h-[380px] lg:max-h-[420px] overflow-y-auto pr-1 space-y-4 custom-scrollbar">
        {filteredGroups.length === 0 ? (
          <p className="py-6 text-center text-xs text-white/50">
            No matching templates found for &ldquo;{searchQuery}&rdquo;.
          </p>
        ) : (
          filteredGroups.map((group) => (
            <div key={group.id} className="space-y-2">
              <div className="flex items-center justify-between">
                <h3 className="text-[11px] font-semibold uppercase tracking-wider text-white/60">
                  {group.label}
                </h3>
                <span className="text-[10px] text-white/40">
                  {group.mainTemplates.length +
                    (showSubcategories ? group.subcategories.length : 0)}{" "}
                  templates
                </span>
              </div>

              {group.mainTemplates.length > 0 && (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-1.5">
                  {group.mainTemplates.map((tpl) => (
                    <SuggestionCard
                      key={tpl}
                      label={`${group.label} (All)`}
                      template={tpl}
                      onUseTemplate={onUseTemplate}
                    />
                  ))}
                </div>
              )}

              {showSubcategories && group.subcategories.length > 0 && (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-1.5 pt-0.5">
                  {group.subcategories.map((sub) => (
                    <SuggestionCard
                      key={sub.template}
                      label={`${group.label} · ${sub.name}`}
                      template={sub.template}
                      onUseTemplate={onUseTemplate}
                    />
                  ))}
                </div>
              )}
            </div>
          ))
        )}
      </div>
    </aside>
  );
}
