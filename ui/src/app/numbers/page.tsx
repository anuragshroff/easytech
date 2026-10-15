"use client";

import { Copy, Pencil, Phone, Search } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";

import {
  createPhoneNumberApiV1OrganizationsTelephonyConfigsConfigIdPhoneNumbersPost,
  getWorkflowsSummaryApiV1WorkflowSummaryGet,
  listPhoneNumbersApiV1OrganizationsTelephonyConfigsConfigIdPhoneNumbersGet,
  listTelephonyConfigurationsApiV1OrganizationsTelephonyConfigsGet,
  searchAvailablePhoneNumbersApiV1OrganizationsTelephonyConfigsConfigIdPhoneNumbersSearchGet,
  updatePhoneNumberApiV1OrganizationsTelephonyConfigsConfigIdPhoneNumbersPhoneNumberIdPut,
} from "@/client/sdk.gen";
import type {
  AvailablePhoneNumberResponse,
  PhoneNumberResponse,
  TelephonyConfigurationListItem,
} from "@/client/types.gen";
import { PageLayout, PageSection } from "@/components/layout/PageLayout";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { detailFromError } from "@/lib/apiError";
import { useAuth } from "@/lib/auth";
import { copyTextToClipboard } from "@/lib/clipboard";

const NO_WORKFLOW = "__none__";

type NumberRow = PhoneNumberResponse & { configName: string };

export default function NumbersDashboardPage() {
  const { user, getAccessToken, loading: authLoading } = useAuth();

  const [configs, setConfigs] = useState<TelephonyConfigurationListItem[]>([]);
  const [workflows, setWorkflows] = useState<{ id: number; name: string }[]>([]);
  const [numbers, setNumbers] = useState<NumberRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [configFilter, setConfigFilter] = useState<string>("all");

  const [searchConfigId, setSearchConfigId] = useState<number | null>(null);
  const [searchOpen, setSearchOpen] = useState(false);
  const [searching, setSearching] = useState(false);
  const [searchResults, setSearchResults] = useState<AvailablePhoneNumberResponse[]>([]);
  const [areaCode, setAreaCode] = useState("");
  const [contains, setContains] = useState("");

  const [assignTarget, setAssignTarget] = useState<NumberRow | null>(null);
  const [assignWorkflowId, setAssignWorkflowId] = useState<string>(NO_WORKFLOW);
  const [buying, setBuying] = useState<string | null>(null);
  const [assigning, setAssigning] = useState(false);

  const fetchAll = useCallback(async () => {
    if (authLoading || !user) return;
    setLoading(true);
    try {
      const token = await getAccessToken();
      const [cfgRes, wfRes] = await Promise.all([
        listTelephonyConfigurationsApiV1OrganizationsTelephonyConfigsGet({
          headers: { Authorization: `Bearer ${token}` },
        }),
        getWorkflowsSummaryApiV1WorkflowSummaryGet({
          headers: { Authorization: `Bearer ${token}` },
          query: { status: "active" },
        }),
      ]);
      if (cfgRes.error) throw new Error(detailFromError(cfgRes.error));
      if (wfRes.error) throw new Error(detailFromError(wfRes.error));

      const allConfigs = cfgRes.data?.configurations ?? [];
      setConfigs(allConfigs);
      setWorkflows((wfRes.data ?? []).map((w) => ({ id: w.id, name: w.name })));

      // The list endpoint is per-config; fan out then flatten for an org view.
      const results = await Promise.all(
        allConfigs.map((c) =>
          listPhoneNumbersApiV1OrganizationsTelephonyConfigsConfigIdPhoneNumbersGet({
            headers: { Authorization: `Bearer ${token}` },
            path: { config_id: c.id },
          }).then((r) => ({ error: r.error, items: r.data?.phone_numbers ?? [], name: c.name })),
        ),
      );
      const firstError = results.find((r) => r.error)?.error;
      if (firstError) throw new Error(detailFromError(firstError));

      setNumbers(
        results.flatMap((r) => r.items.map((n) => ({ ...n, configName: r.name }))),
      );
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to load numbers");
    } finally {
      setLoading(false);
    }
  }, [authLoading, user, getAccessToken]);

  useEffect(() => {
    fetchAll();
  }, [fetchAll]);

  const filteredNumbers =
    configFilter === "all"
      ? numbers
      : numbers.filter((n) => String(n.telephony_configuration_id) === configFilter);

  const openSearch = (configId: number) => {
    setSearchConfigId(configId);
    setSearchResults([]);
    setAreaCode("");
    setContains("");
    setSearchOpen(true);
  };

  const runSearch = async () => {
    if (!searchConfigId) return;
    setSearching(true);
    try {
      const token = await getAccessToken();
      const res = await searchAvailablePhoneNumbersApiV1OrganizationsTelephonyConfigsConfigIdPhoneNumbersSearchGet(
        {
          headers: { Authorization: `Bearer ${token}` },
          path: { config_id: searchConfigId },
          query: {
            country_code: "US",
            area_code: areaCode || undefined,
            contains: contains || undefined,
            limit: 20,
          },
        },
      );
      if (res.error) throw new Error(detailFromError(res.error));
      setSearchResults(res.data?.numbers ?? []);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Search failed");
    } finally {
      setSearching(false);
    }
  };

  const beginAssign = (n: NumberRow) => {
    setAssignTarget(n);
    setAssignWorkflowId(n.inbound_workflow_id ? String(n.inbound_workflow_id) : NO_WORKFLOW);
  };

  const confirmAssign = async () => {
    if (!assignTarget) return;
    setAssigning(true);
    try {
      const token = await getAccessToken();
      const res = await updatePhoneNumberApiV1OrganizationsTelephonyConfigsConfigIdPhoneNumbersPhoneNumberIdPut(
        {
          headers: { Authorization: `Bearer ${token}` },
          path: {
            config_id: assignTarget.telephony_configuration_id,
            phone_number_id: assignTarget.id,
          },
          body:
            assignWorkflowId === NO_WORKFLOW
              ? { clear_inbound_workflow: true }
              : { inbound_workflow_id: Number(assignWorkflowId) },
        },
      );
      if (res.error) throw new Error(detailFromError(res.error));
      toast.success("Agent assigned");
      setAssignTarget(null);
      fetchAll();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to assign agent");
    } finally {
      setAssigning(false);
    }
  };

  const buyNumber = async (configId: number, address: string) => {
    setBuying(address);
    try {
      const token = await getAccessToken();
      const res = await createPhoneNumberApiV1OrganizationsTelephonyConfigsConfigIdPhoneNumbersPost(
        {
          headers: { Authorization: `Bearer ${token}` },
          path: { config_id: configId },
          body: { address },
        },
      );
      if (res.error) throw new Error(detailFromError(res.error));
      toast.success(`Purchased ${address}`);
      setSearchOpen(false);
      fetchAll();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to purchase");
    } finally {
      setBuying(null);
    }
  };
  return (
    <PageLayout
      title="Phone numbers"
      description="Every number across your telephony configurations. Assign an agent in one click."
      actions={
        <Select value={configFilter} onValueChange={setConfigFilter}>
          <SelectTrigger className="w-[220px]">
            <SelectValue placeholder="All configurations" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All configurations</SelectItem>
            {configs.map((c) => (
              <SelectItem key={c.id} value={String(c.id)}>
                {c.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      }
    >
      <PageSection
        title="Numbers"
        description="Every number across your telephony configurations."
        actions={
          <div className="flex flex-wrap items-center gap-2">
            {configs.map((c) => (
              <Button
                key={c.id}
                size="sm"
                variant="outline"
                onClick={() => openSearch(c.id)}
              >
                <Search className="h-4 w-4 mr-2" /> Search DIDs ({c.name})
              </Button>
            ))}
          </div>
        }
      >
        {loading ? (
          <div className="space-y-2">
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
          </div>
        ) : filteredNumbers.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No phone numbers yet. Use “Search DIDs” to buy one, or add a number from a
            configuration.
          </p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Address</TableHead>
                <TableHead>Configuration</TableHead>
                <TableHead>Type</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Agent</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredNumbers.map((n) => (
                <TableRow key={`${n.telephony_configuration_id}-${n.id}`}>
                  <TableCell className="font-mono">
                    <div className="flex items-center gap-1">
                      <Phone className="h-3 w-3 text-muted-foreground" />
                      <span>{n.address}</span>
                      <button
                        type="button"
                        onClick={() => {
                          copyTextToClipboard(String(n.id))
                            .then(() => toast.success("Number ID copied"))
                            .catch(() => toast.error("Failed to copy ID"));
                        }}
                        title="Copy number ID"
                        aria-label={`Copy number ID ${n.id}`}
                        className="text-muted-foreground hover:text-foreground"
                      >
                        <Copy className="h-3 w-3" />
                      </button>
                    </div>
                  </TableCell>
                  <TableCell>
                    <Link
                      href={`/telephony-configurations/${n.telephony_configuration_id}`}
                      className="text-sm hover:underline"
                    >
                      {n.configName}
                    </Link>
                  </TableCell>
                  <TableCell>
                    <Badge variant="outline">{n.address_type}</Badge>
                  </TableCell>
                  <TableCell>
                    <div className="flex flex-wrap gap-1">
                      {n.is_active ? (
                        <Badge variant="secondary">Active</Badge>
                      ) : (
                        <Badge variant="outline">Inactive</Badge>
                      )}
                      {n.is_default_caller_id && <Badge>Default</Badge>}
                    </div>
                  </TableCell>
                  <TableCell>
                    {n.inbound_workflow_id ? (
                      <Link
                        href={`/workflow/${n.inbound_workflow_id}`}
                        className="inline-flex items-center gap-1 hover:underline"
                      >
                        <span>#{n.inbound_workflow_id}</span>
                        {n.inbound_workflow_name && (
                          <span
                            className="truncate max-w-[160px] text-muted-foreground"
                            title={n.inbound_workflow_name}
                          >
                            {n.inbound_workflow_name.length > 20
                              ? `${n.inbound_workflow_name.slice(0, 20)}…`
                              : n.inbound_workflow_name}
                          </span>
                        )}
                      </Link>
                    ) : (
                      <span className="text-muted-foreground">Unassigned</span>
                    )}
                  </TableCell>
                  <TableCell className="text-right">
                    <Button variant="ghost" size="sm" onClick={() => beginAssign(n)}>
                      <Pencil className="h-4 w-4 mr-2" /> Assign agent
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </PageSection>

      <Dialog open={searchOpen} onOpenChange={setSearchOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Buy a phone number</DialogTitle>
            <DialogDescription>
              Search this carrier account for purchasable DIDs, then buy one. It is added
              to the configuration and its webhook is bound automatically.
            </DialogDescription>
          </DialogHeader>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1">
              <Label htmlFor="num-area">Area code</Label>
              <Input
                id="num-area"
                placeholder="e.g. 415"
                value={areaCode}
                onChange={(e) => setAreaCode(e.target.value)}
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="num-contains">Contains</Label>
              <Input
                id="num-contains"
                placeholder="e.g. 123"
                value={contains}
                onChange={(e) => setContains(e.target.value)}
              />
            </div>
          </div>
          <div className="flex justify-end">
            <Button onClick={runSearch} disabled={searching}>
              {searching ? "Searching..." : "Search"}
            </Button>
          </div>
          {searchResults.length > 0 && (
            <div className="max-h-80 overflow-auto rounded border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Number</TableHead>
                    <TableHead>Location</TableHead>
                    <TableHead>Features</TableHead>
                    <TableHead className="text-right">Action</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {searchResults.map((r) => (
                    <TableRow key={r.phone_number}>
                      <TableCell className="font-mono">{r.phone_number}</TableCell>
                      <TableCell className="text-muted-foreground">
                        {r.locality || r.region || "—"}
                      </TableCell>
                      <TableCell className="text-muted-foreground">
                        {Object.entries(r.capabilities ?? {})
                          .filter(([, v]) => v)
                          .map(([k]) => k)
                          .join(", ") || "—"}
                      </TableCell>
                      <TableCell className="text-right">
                        <Button
                          size="sm"
                          onClick={() => buyNumber(searchConfigId!, r.phone_number)}
                          disabled={buying !== null}
                        >
                          {buying === r.phone_number ? "Buying..." : "Buy"}
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setSearchOpen(false)}>
              Close
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={!!assignTarget} onOpenChange={(o) => !o && setAssignTarget(null)}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Assign agent</DialogTitle>
            <DialogDescription>
              Choose which voice agent answers inbound calls on{" "}
              <span className="font-mono">{assignTarget?.address}</span>.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-1">
            <Label htmlFor="num-workflow">Voice agent</Label>
            <Select value={assignWorkflowId} onValueChange={setAssignWorkflowId}>
              <SelectTrigger id="num-workflow">
                <SelectValue placeholder="(none)" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={NO_WORKFLOW}>(none)</SelectItem>
                {workflows.map((w) => (
                  <SelectItem key={w.id} value={String(w.id)}>
                    #{w.id} - {w.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setAssignTarget(null)}
              disabled={assigning}
            >
              Cancel
            </Button>
            <Button onClick={confirmAssign} disabled={assigning}>
              {assigning ? "Saving..." : "Save"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </PageLayout>
  );
}
